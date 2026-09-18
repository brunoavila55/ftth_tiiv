import * as React from "react";
import { cancelJob, getJob } from "../api";
import type { JobRead, JobStatus } from "../types";

export interface UseJobPollingOptions {
  pollIntervalMs?: number;
  onFinish?: (job: JobRead) => void;
}

export function useJobPolling(
  jobId: string | null | undefined,
  options: UseJobPollingOptions = {}
) {
  const { pollIntervalMs = 1500, onFinish } = options;

  const [job, setJob] = React.useState<JobRead | null>(null);
  const [loading, setLoading] = React.useState<boolean>(Boolean(jobId));
  const [error, setError] = React.useState<string | null>(null);
  const [canceling, setCanceling] = React.useState<boolean>(false);

  const isTerminal = (status?: JobStatus): boolean => {
    return status === "succeeded" || status === "failed" || status === "cancelled";
  };

  const fetchJob = React.useCallback(
    async (signal?: AbortSignal) => {
      if (!jobId) return;
      try {
        const data = await getJob(jobId, signal);
        setJob(data);
        setError(null);

        if (isTerminal(data.status) && onFinish) {
          onFinish(data);
        }
      } catch (err: unknown) {
        if ((err as Error)?.name !== "AbortError") {
          setError((err as Error).message || "Falha ao consultar status do job");
        }
      } finally {
        setLoading(false);
      }
    },
    [jobId, onFinish]
  );

  const jobRef = React.useRef<JobRead | null>(job);
  React.useEffect(() => {
    jobRef.current = job;
  }, [job]);

  React.useEffect(() => {
    if (!jobId) {
      setJob(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    const controller = new AbortController();

    fetchJob(controller.signal);

    const timer = setInterval(() => {
      if (jobRef.current && isTerminal(jobRef.current.status)) {
        clearInterval(timer);
        return;
      }
      fetchJob(controller.signal);
    }, pollIntervalMs);

    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [jobId, fetchJob, pollIntervalMs]);

  const handleCancel = React.useCallback(async () => {
    if (!jobId || canceling) return;
    try {
      setCanceling(true);
      const updated = await cancelJob(jobId);
      setJob(updated);
    } catch (err: unknown) {
      setError((err as Error).message || "Falha ao solicitar cancelamento do job");
    } finally {
      setCanceling(false);
    }
  }, [jobId, canceling]);

  return {
    job,
    loading,
    error,
    canceling,
    isFinished: isTerminal(job?.status),
    cancel: handleCancel,
    refetch: () => fetchJob(),
  };
}
