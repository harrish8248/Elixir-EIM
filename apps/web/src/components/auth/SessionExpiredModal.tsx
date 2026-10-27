import React, { useState } from "react";
import { Modal } from "@/design-system/components/Modal";
import { Button } from "@/design-system/components/Button";
import { Input } from "@/design-system/components/Input";
import { Clock, LogIn } from "lucide-react";
import { useAuth } from "@/config/AuthContext";

export const SessionExpiredModal: React.FC = () => {
  const { isSessionExpired, login, user } = useAuth();
  const [password, setPassword] = useState("password123");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isSessionExpired) return null;

  const handleReLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      await login({
        username: user?.email || "sarah.chen@acrocorp.com",
        password,
      });
    } catch (err: any) {
      setError(err.body?.detail || err.message || "Failed to re-authenticate");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      open={isSessionExpired}
      onOpenChange={() => {}}
      title="Session Expired"
      description="Your session has timed out due to inactivity (30-minute idle window). Please re-enter your password to continue."
      maxWidth="sm"
    >
      <form onSubmit={handleReLogin} className="space-y-4">
        <div className="flex items-center gap-3 p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
          <Clock className="w-5 h-5 text-amber-600 shrink-0" />
          <span>Security timeout enforced. Your unsaved context is preserved.</span>
        </div>

        {error && (
          <p className="text-xs text-red-600 font-medium">{error}</p>
        )}

        <div>
          <label className="block text-xs font-semibold text-surface-700 mb-1">
            Password for {user?.email || "current account"}
          </label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
            required
            autoFocus
          />
        </div>

        <Button
          type="submit"
          variant="primary"
          className="w-full"
          isLoading={isLoading}
          icon={<LogIn className="w-4 h-4" />}
        >
          Re-Authenticate & Resume
        </Button>
      </form>
    </Modal>
  );
};
