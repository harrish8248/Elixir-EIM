import React, { useState } from "react";
import { Modal } from "@/design-system/components/Modal";
import { Button } from "@/design-system/components/Button";
import { Input } from "@/design-system/components/Input";
import { KeyRound, ShieldAlert } from "lucide-react";
import { useAuth } from "@/config/AuthContext";

export interface StepUpModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  actionTitle?: string;
  onSuccess?: () => void;
}

export const StepUpModal: React.FC<StepUpModalProps> = ({
  open,
  onOpenChange,
  actionTitle = "Sensitive Action",
  onSuccess,
}) => {
  const { stepUp } = useAuth();
  const [otp, setOtp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await stepUp({ otp_code: otp, reason: actionTitle });
      onOpenChange(false);
      if (onSuccess) onSuccess();
    } catch (err: any) {
      setError(err.body?.detail || err.message || "Invalid MFA code");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Multi-Factor Authentication Step-Up"
      description={`Executing '${actionTitle}' requires secondary step-up authorization pursuant to security policy.`}
      maxWidth="sm"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && (
          <div className="p-2.5 rounded bg-red-50 border border-red-200 text-xs text-red-700 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 shrink-0 text-red-600" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-surface-700 mb-1">
            One-Time Passcode (OTP / Authenticator)
          </label>
          <Input
            type="text"
            value={otp}
            onChange={(e) => setOtp(e.target.value)}
            placeholder="123456"
            className="text-center font-mono text-base tracking-widest"
            maxLength={6}
            required
            autoFocus
          />
          <p className="text-[10px] text-surface-500 mt-1">
            Enter 6-digit TOTP code (or '123456' for Keycloak test realm)
          </p>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)} type="button">
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            isLoading={isLoading}
            icon={<KeyRound className="w-4 h-4" />}
          >
            Verify & Proceed
          </Button>
        </div>
      </form>
    </Modal>
  );
};
