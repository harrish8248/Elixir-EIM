import type { Meta, StoryObj } from "@storybook/react";
import { ErrorState } from "./ErrorState";

const meta: Meta<typeof ErrorState> = {
  title: "Design System/ErrorState",
  component: ErrorState,
};

export default meta;
type Story = StoryObj<typeof ErrorState>;

export const Default: Story = {
  args: {
    title: "Database Connection Failure",
    message: "PostgreSQL transaction timed out while acquiring row-level security lock.",
    errorCode: "DB_TIMEOUT_504",
    errorDetails: "sqlalchemy.exc.TimeoutError: QueuePool limit of size 20 overflow 10 reached",
    onRetry: () => alert("Retrying..."),
  },
};
