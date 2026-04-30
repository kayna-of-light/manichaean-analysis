"""
Shared base class for Kephalaia v2 LLM pipeline stages.

Extracts the common structural patterns from translate_kephalaia_v2.py:
- Azure/Anthropic client setup with thinking
- Streaming with tool calls + retry logic
- CLI argument parsing (shared flags)
- Parallel execution via ThreadPoolExecutor
- Page selection and skip-existing logic
- Thread-safe output writing
- Progress reporting

Each stage subclasses PipelineStage and provides:
- stage_name, description
- tool schema + system prompt
- input/output path logic
- build_user_message() for each page
- process_result() for post-processing
"""
import argparse
import json
import os
import re
import sys
import time
import traceback
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

import httpx
from anthropic import AnthropicFoundry
from dotenv import dotenv_values
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PROJECT_DIR = REPO_ROOT / "output" / "projects" / "kephalaia_v2"
PAGES_DIR = PROJECT_DIR / "pages"
SCORES_DIR = PROJECT_DIR / "scores"
SECRETS_PATH = REPO_ROOT / "secrets" / "azure_openai.env"


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def create_client() -> tuple[AnthropicFoundry, str]:
    """Create the AnthropicFoundry client from credentials.

    Returns (client, deployment_name).
    """
    if not SECRETS_PATH.exists():
        print(f"ERROR: Secrets file not found at {SECRETS_PATH}")
        sys.exit(1)
    config = dotenv_values(SECRETS_PATH)
    endpoint = config.get("ANTHROPIC_ENDPOINT", "").rstrip("/")
    api_key = config.get("ANTHROPIC_API_KEY", "")
    deployment = config.get("ANTHROPIC_DEPLOYMENT", "claude-opus-4-7-1")

    if not endpoint or not api_key:
        print("ERROR: ANTHROPIC_ENDPOINT and ANTHROPIC_API_KEY required")
        sys.exit(1)

    old_resource = os.environ.pop("ANTHROPIC_FOUNDRY_RESOURCE", None)
    try:
        client = AnthropicFoundry(
            api_key=api_key,
            base_url=endpoint,
            timeout=httpx.Timeout(1800.0, connect=30.0),
        )
    finally:
        if old_resource is not None:
            os.environ["ANTHROPIC_FOUNDRY_RESOURCE"] = old_resource

    return client, deployment


# ---------------------------------------------------------------------------
# Streaming tool-call execution with retry
# ---------------------------------------------------------------------------

def stream_tool_call(
    client: AnthropicFoundry,
    deployment: str,
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    tool_name: str,
    effort: str = "xhigh",
    max_tokens: int = 128_000,
    max_retries: int = 5,
    page_label: str = "",
    debug: bool = False,
) -> dict | None:
    """Stream a message expecting a single tool call, with retry logic.

    Args:
        client: AnthropicFoundry instance
        deployment: Model deployment name
        system: System prompt
        messages: Conversation messages
        tools: Tool definitions (JSON Schema format)
        tool_name: Expected tool name to extract
        effort: Thinking effort level
        max_tokens: Maximum output tokens
        max_retries: Number of retries on failure
        page_label: Label for progress output (e.g. "p.35")
        debug: Whether to print thinking/streaming details

    Returns:
        The tool input dict, or None on failure.
    """
    thinking_config = {
        "type": "adaptive",
        "display": "summarized" if debug else "omitted",
    }

    kwargs: dict[str, Any] = dict(
        model=deployment,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=max_tokens,
        thinking=thinking_config,
    )
    if effort != "xhigh":
        kwargs["output_config"] = {"effort": effort}

    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.time()
            tool_input = None
            text_parts: list[str] = []
            event_count = 0

            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    event_count += 1
                    etype = getattr(event, "type", "")

                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        btype = (
                            getattr(block, "type", "") if block else ""
                        )
                        if debug:
                            elapsed = time.time() - t0
                            print(
                                f"\n  [{btype} {elapsed:.0f}s]",
                                end="", flush=True,
                            )

                    elif etype == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta:
                            dtype = getattr(delta, "type", "")
                            if dtype == "text_delta":
                                chunk = getattr(delta, "text", "") or ""
                                text_parts.append(chunk)
                            elif dtype == "thinking_delta":
                                if debug:
                                    chunk = (
                                        getattr(delta, "thinking", "")
                                        or ""
                                    )
                                    sys.stdout.write(chunk)
                                    sys.stdout.flush()
                            elif dtype == "signature_delta":
                                if debug:
                                    elapsed = time.time() - t0
                                    print(
                                        f" sig@{elapsed:.0f}s",
                                        end="", flush=True,
                                    )

                    elif etype == "content_block_stop":
                        if debug:
                            elapsed = time.time() - t0
                            print(f" done@{elapsed:.0f}s", flush=True)

                final_msg = stream.get_final_message()

            elapsed = time.time() - t0

            if debug:
                print(
                    f"  {elapsed:.0f}s"
                    f" (in={final_msg.usage.input_tokens}"
                    f" out={final_msg.usage.output_tokens}"
                    f" events={event_count})",
                    flush=True,
                )

            # Extract tool call
            for block in final_msg.content:
                btype = getattr(block, "type", "")
                if btype == "tool_use" and block.name == tool_name:
                    tool_input = block.input

            # Detect truncation
            stop = getattr(final_msg, "stop_reason", None)
            truncated = stop == "max_tokens" or (
                tool_input is not None
                and not _looks_complete(tool_input)
            )
            if truncated:
                out_tokens = getattr(
                    getattr(final_msg, "usage", None),
                    "output_tokens", "?"
                )
                print(
                    f"\n  WARNING: Truncated {page_label} "
                    f"({out_tokens} tokens). Retrying..."
                )
                tool_input = None
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

            if tool_input is None:
                text_output = "".join(text_parts).strip()
                print(
                    f"  WARNING: No {tool_name} call for {page_label}."
                )
                if text_output and debug:
                    print(f"  Text: {text_output[:300]}")
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

            return tool_input

        except (httpx.RemoteProtocolError, httpx.ReadError,
                httpx.ReadTimeout, ConnectionError, OSError) as e:
            print(
                f"\n  Connection error {page_label}, "
                f"attempt {attempt}/{max_retries}: {e}"
            )
            if attempt < max_retries:
                time.sleep(5 * attempt)
                continue
            return None

        except Exception as e:
            err_str = str(e)
            if "content_filter" in err_str.lower():
                print(
                    f"  Content filter {page_label}, "
                    f"attempt {attempt}/{max_retries}"
                )
                if attempt < max_retries:
                    time.sleep(attempt * 10)
                    continue
            elif "rate" in err_str.lower() or "429" in err_str:
                wait = 60.0 * attempt
                print(f"  Rate limit, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            elif "overloaded" in err_str.lower() or "529" in err_str:
                wait = 30.0 * attempt
                print(f"  Overloaded, waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            else:
                print(f"  ERROR {page_label}: {e}")
                if debug:
                    traceback.print_exc()
                if attempt < max_retries:
                    time.sleep(attempt * 5)
                    continue
                return None

    return None


def _looks_complete(tool_input: dict) -> bool:
    """Heuristic: does the tool_input look like a complete response?"""
    # If it has a "page" key, it's likely from translate
    if "page" in tool_input:
        return True
    # If it has any required-looking keys, assume complete
    if len(tool_input) >= 2:
        return True
    return False


# ---------------------------------------------------------------------------
# Base class for pipeline stages
# ---------------------------------------------------------------------------

_write_lock = Lock()


class PipelineStage(ABC):
    """Base class for LLM pipeline stages.

    Subclass and implement the abstract methods to create a new stage.
    The base handles: CLI parsing, page selection, parallelism, client
    setup, streaming, retry, and progress reporting.
    """

    # --- Subclass must set these ---
    stage_name: str = "unnamed"
    stage_number: int = 0
    description: str = ""
    tool_name: str = ""
    tool_schema: dict = {}
    item_name: str = "page"
    item_name_plural: str = "pages"
    item_prefix: str = "p"

    def __init__(self) -> None:
        self.client: AnthropicFoundry | None = None
        self.deployment: str = ""
        self.args: argparse.Namespace | None = None
        self.debug: bool = False

    # --- Abstract methods ---

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this stage."""
        ...

    @abstractmethod
    def get_input_dir(self) -> Path:
        """Return the directory containing input files for this stage."""
        ...

    @abstractmethod
    def get_output_dir(self) -> Path:
        """Return the directory for this stage's output."""
        ...

    @abstractmethod
    def build_user_message(self, page_num: int) -> str:
        """Build the user message for a specific page.

        Load whatever inputs the stage needs and format the prompt.
        """
        ...

    @abstractmethod
    def process_result(self, page_num: int, result: dict) -> dict:
        """Post-process the raw tool output before saving.

        Return the dict to be saved as JSON. Can add metadata,
        validate, or transform.
        """
        ...

    # --- Optional overrides ---

    def list_available(self) -> list[int]:
        """List available page numbers from the input directory.

        Default: looks for p_NNN.json in input_dir.
        """
        input_dir = self.get_input_dir()
        pages = []
        for path in sorted(input_dir.glob("p_*.json")):
            m = re.match(r"p_(\d+)\.json", path.name)
            if m:
                pages.append(int(m.group(1)))
        return pages

    def is_done(self, page_num: int) -> bool:
        """Check if output already exists for this page."""
        return (
            self.get_output_dir() / f"{self.item_prefix}_{page_num:03d}.json"
        ).exists()

    def save_output(self, page_num: int, data: dict) -> None:
        """Save the output JSON for a page (thread-safe)."""
        output_dir = self.get_output_dir()
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{self.item_prefix}_{page_num:03d}.json"
        with _write_lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    def load_page_json(self, page_num: int, source_dir: Path) -> dict | None:
        """Load a page JSON from a given directory."""
        path = source_dir / f"{self.item_prefix}_{page_num:03d}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def format_summary(self, page_num: int, result: dict) -> str:
        """Format a one-line summary after processing a page.

        Override for stage-specific summaries.
        """
        return "OK"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add stage-specific CLI arguments (optional override)."""
        pass

    # --- Core execution ---

    def parse_args(self) -> argparse.Namespace:
        """Parse CLI arguments with shared + stage-specific flags."""
        parser = argparse.ArgumentParser(
            description=f"Stage {self.stage_number}: {self.description}"
        )
        # Shared arguments
        parser.add_argument(
            "--page", "-p", type=int, nargs="+", default=None,
            help=f"{self.item_name.title()} number(s) to process",
        )
        parser.add_argument("--range", "-r", type=str, default=None)
        parser.add_argument("--limit", "-l", type=int, default=None)
        parser.add_argument("--dry-run", "-n", action="store_true")
        parser.add_argument("--overwrite", action="store_true")
        parser.add_argument(
            "--effort", default="xhigh",
            choices=["low", "medium", "high", "xhigh", "max"],
        )
        parser.add_argument("--debug", action="store_true")
        parser.add_argument(
            "--max-concurrency", "-j", type=int, default=1,
        )
        # Stage-specific arguments
        self.add_arguments(parser)
        return parser.parse_args()

    def select_pages(self, all_pages: list[int]) -> list[int]:
        """Apply CLI filters to determine which pages to process."""
        args = self.args

        if args.page is not None:
            requested = set(args.page)
            pages = [p for p in all_pages if p in requested]
            missing = requested - set(pages)
            if missing:
                print(
                    f"ERROR: {self.item_name_plural.title()} "
                    f"not found: {sorted(missing)}"
                )
                sys.exit(1)
        elif args.range:
            m = re.match(r"(\d+)-(\d+)", args.range)
            if not m:
                print("ERROR: Invalid range. Use '10-50'")
                sys.exit(1)
            start, end = int(m.group(1)), int(m.group(2))
            pages = [p for p in all_pages if start <= p <= end]
        else:
            pages = all_pages

        if args.limit:
            pages = pages[:args.limit]

        # Skip already processed
        if not args.overwrite:
            to_process = [p for p in pages if not self.is_done(p)]
            skipped = len(pages) - len(to_process)
            if skipped > 0:
                print(
                    f"  Skipping {skipped} already done "
                    f"(use --overwrite)"
                )
            pages = to_process

        return pages

    def _process_one(self, page_num: int) -> tuple[int, dict | None]:
        """Process a single page: build prompt, call LLM, return result."""
        user_msg = self.build_user_message(page_num)
        if user_msg is None:
            return page_num, None

        result = stream_tool_call(
            self.client,
            self.deployment,
            system=self.get_system_prompt(),
            messages=[{"role": "user", "content": user_msg}],
            tools=[self.tool_schema],
            tool_name=self.tool_name,
            effort=self.args.effort,
            max_tokens=128_000,
            page_label=f"{self.item_prefix}.{page_num}",
            debug=self.debug,
        )
        return page_num, result

    def run(self) -> None:
        """Main execution entry point."""
        self.args = self.parse_args()
        self.debug = self.args.debug

        print(f"Stage {self.stage_number}: {self.stage_name}")
        print(f"  {self.description}")
        print(f"  Input:  {self.get_input_dir()}")
        print(f"  Output: {self.get_output_dir()}")

        all_pages = self.list_available()
        if not all_pages:
            print(f"\nERROR: No input files in {self.get_input_dir()}")
            sys.exit(1)
        print(
            f"\nFound {len(all_pages)} input {self.item_name_plural} "
            f"({self.item_prefix}.{all_pages[0]}-"
            f"{self.item_prefix}.{all_pages[-1]})"
        )

        pages = self.select_pages(all_pages)
        if not pages:
            print(f"All requested {self.item_name_plural} already processed.")
            return

        print(f"\nProcessing {len(pages)} {self.item_name_plural}:")
        for p in pages:
            print(f"  {self.item_prefix}.{p:3d}")

        if self.args.dry_run:
            print(f"\n[DRY RUN] No API calls made.")
            return

        # Create client
        self.client, self.deployment = create_client()
        print(f"\nDeployment: {self.deployment}")
        print(f"Thinking effort: {self.args.effort}")
        print()

        self.get_output_dir().mkdir(parents=True, exist_ok=True)

        concurrency = max(1, self.args.max_concurrency)
        results: list[dict] = []
        errors: list[int] = []

        if concurrency == 1:
            for i, page_num in enumerate(pages, 1):
                print(
                    f"[{i}/{len(pages)}] {self.item_prefix}.{page_num}...",
                    end=" ", flush=True,
                )
                _, result = self._process_one(page_num)

                if result is None:
                    print("FAILED")
                    errors.append(page_num)
                    continue

                processed = self.process_result(page_num, result)
                self.save_output(page_num, processed)
                summary = self.format_summary(page_num, processed)
                print(summary)
                results.append(processed)

                if i < len(pages):
                    time.sleep(0.5)
        else:
            print(f"Running with {concurrency} parallel workers\n", flush=True)

            pbar = tqdm(
                total=len(pages),
                desc=f"Stage {self.stage_number}",
                unit=self.item_name,
                file=sys.stdout,
            )

            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {
                    executor.submit(self._process_one, p): p
                    for p in pages
                }
                for future in as_completed(futures):
                    page_num = futures[future]
                    try:
                        pn, result = future.result()
                    except Exception as e:
                        pbar.write(
                            f"  {self.item_prefix}.{page_num}: "
                            f"EXCEPTION — {e}"
                        )
                        errors.append(page_num)
                        pbar.update(1)
                        continue
                    if result is None:
                        pbar.write(
                            f"  {self.item_prefix}.{page_num}: FAILED"
                        )
                        errors.append(page_num)
                        pbar.update(1)
                        continue
                    processed = self.process_result(page_num, result)
                    self.save_output(page_num, processed)
                    summary = self.format_summary(page_num, processed)
                    pbar.write(
                        f"  {self.item_prefix}.{page_num}: {summary}"
                    )
                    results.append(processed)
                    pbar.update(1)

            pbar.close()

        # Summary
        print(f"\n{'='*50}")
        print(f"STAGE {self.stage_number} COMPLETE: {self.stage_name}")
        print(f"  Processed: {len(results)} {self.item_name_plural}")
        if errors:
            print(f"  Failed:    {len(errors)} {self.item_name_plural} — {errors}")
