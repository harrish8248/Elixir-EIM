import type { Meta, StoryObj } from "@storybook/react";
import { Toast } from "./Toast";

const meta: Meta<typeof Toast> = {
  title: "Design System/Toast",
  component: Toast,
};

export default meta;
type Story = StoryObj<typeof Toast>;

export const Success: Story = {
  args: {
    type: "success",
    title: "Retention Plan Published",
    message: "File plan v2.4 applied across all 18 workspaces.",
  },
};

export const Error: Story = {
  args: {
    type: "error",
    title: "Authorization Failure (PDP Deny)",
    message: "Insufficient security clearance: Restricted classification required.",
  },
};
