import React from "react";
import { AuthProvider, useAuth } from "@/config/AuthContext";
import { AppShell } from "@/components/shell/AppShell";
import { LoginView } from "@/components/auth/LoginView";
import { SessionExpiredModal } from "@/components/auth/SessionExpiredModal";
import "@/design-system/index.css";

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen w-screen flex flex-col items-center justify-center bg-surface-100">
        <div className="w-8 h-8 border-3 border-brand-900 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-xs font-medium text-surface-600">Bootstrapping enterprise identity & session...</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginView />;
  }

  return (
    <>
      <AppShell />
      <SessionExpiredModal />
    </>
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
