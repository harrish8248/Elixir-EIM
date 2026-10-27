import type { Meta, StoryObj } from "@storybook/react";
import { ConfirmDialog } from "./ConfirmDialog";

const meta: Meta<typeof ConfirmDialog> = {
  title: "Design System/ConfirmDialog",
  component: ConfirmDialog,
};

export default meta;
type Story = StoryObj<typeof ConfirmDialog>;

export const DangerVariant: Story = {
  args: {
    open: true,
    title: "Revoke API Secret",
    message: "Revoking this API bearer token will immediately cut off external SCIM synchronization.",
    confirmLabel: "Revoke Secret",
    variant: "danger",
    onConfirm: () => alert("Confirmed"),
  },
};
