import React, { useState } from "react";
import { useAuth } from "@/config/AuthContext";
import { Button } from "@/design-system/components/Button";
import { Input } from "@/design-system/components/Input";
import { Shield, Lock, ArrowRight, UserCheck } from "lucide-react";
import { BRANDING } from "@/config/branding";

export const LoginView: React.FC = () => {
  const { login, isLoading } = useAuth();
  const [username, setUsername] = useState("sarah.chen@acrocorp.com");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login({ username, password });
    } catch (err: any) {
      setError(err.body?.detail || err.message || "Authentication failed");
    }
  };

  const handleQuickLogin = async (userEmail: string) => {
    setUsername(userEmail);
    setError(null);
    try {
      await login({ username: userEmail, password: "password123" });
    } catch (err: any) {
      setError(err.body?.detail || err.message || "Authentication failed");
    }
  };

  return (
    <div className="min-h-screen w-screen flex flex-col justify-center items-center bg-surface-100 p-4">
      <div className="w-full max-w-md bg-surface-50 rounded-xl shadow-xl border border-surface-200 p-8">
        <div className="flex flex-col items-center mb-6">
          <div className="w-12 h-12 rounded-xl bg-brand-900 text-white flex items-center justify-center mb-3 shadow-md">
            <Shield className="w-6 h-6 text-brand-300" />
          </div>
          <h1 className="text-xl font-bold text-surface-900 tracking-tight">{BRANDING.name}</h1>
          <p className="text-xs text-surface-500 mt-1">Enterprise Information Management & Trust Ledger</p>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-md bg-red-50 border border-red-200 text-xs text-red-700 flex items-center gap-2">
            <Lock className="w-4 h-4 shrink-0 text-red-600" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">
              Enterprise Email / Username
            </label>
            <Input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="user@acrocorp.com"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-surface-700 mb-1">
              Password
            </label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            size="lg"
            className="w-full mt-2"
            isLoading={isLoading}
            icon={<ArrowRight className="w-4 h-4" />}
          >
            Authenticate with Keycloak
          </Button>
        </form>

        <div className="mt-6 pt-5 border-t border-surface-200">
          <p className="text-[11px] font-medium text-surface-500 mb-2">Test Enterprise Personas (Pre-seeded):</p>
          <div className="flex flex-col gap-1.5">
            <button
              onClick={() => handleQuickLogin("sarah.chen@acrocorp.com")}
              className="flex items-center justify-between p-2 rounded text-xs bg-surface-100 hover:bg-surface-200 text-surface-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <UserCheck className="w-3.5 h-3.5 text-brand-700" />
                <span className="font-medium">Sarah Chen (Admin, global)</span>
              </div>
              <span className="text-[10px] text-surface-500">Global Admin · Clearance 3</span>
            </button>

            <button
              onClick={() => handleQuickLogin("raj.patel@acrocorp.com")}
              className="flex items-center justify-between p-2 rounded text-xs bg-surface-100 hover:bg-surface-200 text-surface-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <UserCheck className="w-3.5 h-3.5 text-blue-700" />
                <span className="font-medium">Raj Patel (Finance, acro-finance)</span>
              </div>
              <span className="text-[10px] text-surface-500">Finance · Clearance 2</span>
            </button>

            <button
              onClick={() => handleQuickLogin("maria.santos@acrocorp.com")}
              className="flex items-center justify-between p-2 rounded text-xs bg-surface-100 hover:bg-surface-200 text-surface-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <UserCheck className="w-3.5 h-3.5 text-purple-700" />
                <span className="font-medium">Maria Santos (HR, acro-hr)</span>
              </div>
              <span className="text-[10px] text-surface-500">HR · Clearance 1</span>
            </button>

            <button
              onClick={() => handleQuickLogin("alex.auditor@acrocorp.com")}
              className="flex items-center justify-between p-2 rounded text-xs bg-surface-100 hover:bg-surface-200 text-surface-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <UserCheck className="w-3.5 h-3.5 text-amber-700" />
                <span className="font-medium">Alex Auditor (Auditor)</span>
              </div>
              <span className="text-[10px] text-surface-500">Compliance · Clearance 3</span>
            </button>

            <button
              onClick={() => handleQuickLogin("admin@acrocorp.com")}
              className="flex items-center justify-between p-2 rounded text-xs bg-surface-100 hover:bg-surface-200 text-surface-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <UserCheck className="w-3.5 h-3.5 text-red-700" />
                <span className="font-medium">Admin (System Admin)</span>
              </div>
              <span className="text-[10px] text-surface-500">IT · Clearance 5</span>
            </button>
          </div>
        </div>
      </div>

      <p className="mt-4 text-xs text-surface-400">
        Secured with OIDC Authorization Code + PKCE, cached JWKS verification & PostgreSQL RLS.
      </p>
    </div>
  );
};
