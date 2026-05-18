"use client";
import { useEffect, useState } from "react";
import {
  Box,
  Paper,
  Stack,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import { PagesOverview } from "@/components/reviewer/PagesOverview";
import { ClustersOverview } from "@/components/cluster/ClustersOverview";
import { EditorialOverview } from "@/components/editorial/EditorialOverview";

type HomeTab = "pages" | "clusters" | "editorial";

const STORAGE_KEY = "manual_reviewer.home_tab";

export default function Page() {
  const [tab, setTab] = useState<HomeTab>("pages");

  // Persist tab selection across reloads.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "pages" || saved === "clusters" || saved === "editorial") setTab(saved);
  }, []);

  const onChange = (_e: React.SyntheticEvent, value: HomeTab) => {
    setTab(value);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, value);
    }
  };

  return (
    <Box sx={{ maxWidth: 1300, mx: "auto" }}>
      <Paper elevation={0} sx={{ p: 4, borderRadius: 4 }}>
        <Stack spacing={2}>
          <Box>
            <Typography variant="overline" sx={{ opacity: 0.7 }}>
              Manual Reviewer
            </Typography>
            <Typography variant="h3" sx={{ mt: 0.5 }}>
              Kephalaia
            </Typography>
          </Box>
          <Tabs value={tab} onChange={onChange}>
            <Tab value="pages" label="Pages" />
            <Tab value="clusters" label="Clusters" />
            <Tab value="editorial" label="Editorial" />
          </Tabs>
          {tab === "pages" && <PagesOverview />}
          {tab === "clusters" && <ClustersOverview />}
          {tab === "editorial" && <EditorialOverview />}
        </Stack>
      </Paper>
    </Box>
  );
}
