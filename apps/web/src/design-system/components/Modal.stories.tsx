import type { Meta, StoryObj } from "@storybook/react";
import { Modal } from "./Modal";
import { Button } from "./Button";

const meta: Meta<typeof Modal> = {
  title: "Design System/Modal",
  component: Modal,
};

export default meta;
type Story = StoryObj<typeof Modal>;

export const Default: Story = {
  args: {
    open: true,
    title: "Retention Policy Confirmation",
    description: "Review and approve the 7-year retention rule for Financial Records.",
    children: <p>All matched records will be sealed and held until disposition date.</p>,
    footer: (
      <>
        <Button variant="secondary">Cancel</Button>
        <Button variant="primary">Confirm Policy</Button>
      </>
    ),
  },
};
