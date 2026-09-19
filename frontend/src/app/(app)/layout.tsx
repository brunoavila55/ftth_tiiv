import { AppShell } from "@/components/layout/app-shell";
import { AuthGuard } from "@/components/auth/auth-guard";
import { RoutePermissionGuard } from "@/components/auth/route-permission-guard";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>
        <RoutePermissionGuard>{children}</RoutePermissionGuard>
      </AppShell>
    </AuthGuard>
  );
}
