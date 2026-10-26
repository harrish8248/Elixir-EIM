import { Button } from "./Button";
import { Upload, Lock } from "lucide-react";

export default {
  title: "Design System/Button",
  component: Button,
};

export const Primary = () => <Button variant="primary">Save Document</Button>;
export const Secondary = () => <Button variant="secondary">Cancel</Button>;
export const Danger = () => <Button variant="danger" icon={<Lock className="w-4 h-4" />}>Apply Legal Hold</Button>;
export const WithIcon = () => <Button variant="primary" icon={<Upload className="w-4 h-4" />}>Upload File</Button>;
export const Loading = () => <Button isLoading>Saving Changes...</Button>;
