import type { Meta, StoryObj } from "@storybook/react";
import { Tabs } from "./Tabs";
import { FileText, Shield, Key } from "lucide-react";

const meta: Meta<typeof Tabs> = {
  title: "Design System/Tabs",
  component: Tabs,
};

export default meta;
type Story = StoryObj<typeof Tabs>;

export const Default: Story = {
  args: {
    items: [
      {
        id: "overview",
        label: "Overview",
        icon: <FileText />,
        content: <p className="text-sm">System statistics and tenant overview.</p>,
      },
      {
        id: "security",
        label: "Security & RLS",
        icon: <Shield />,
        badge: "Active",
        content: <p className="text-sm">PostgreSQL Row-Level Security policy controls.</p>,
      },
      {
        id: "tokens",
        label: "SCIM Bearer Tokens",
        icon: <Key />,
        content: <p className="text-sm">Tenant SCIM 2.0 Ingestion Bearer Credentials.</p>,
      },
    ],
  },
};
