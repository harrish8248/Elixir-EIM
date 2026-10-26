import { StatusPill } from "./StatusPill";

export default {
  title: "Design System/StatusPill",
  component: StatusPill,
};

export const LegalHold = () => <StatusPill label="RECORD: HELD" variant="hold" />;
export const OfficialRecord = () => <StatusPill label="OFFICIAL RECORD" variant="record" />;
export const RetentionSchedule = () => <StatusPill label="RETENTION: 7Y" variant="warning" />;
export const Confidential = () => <StatusPill label="CONFIDENTIAL" variant="danger" />;
export const VerifiedClean = () => <StatusPill label="MALWARE SCAN: CLEAN" variant="success" />;
