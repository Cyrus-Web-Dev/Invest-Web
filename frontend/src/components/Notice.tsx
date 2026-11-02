export interface NoticeState { kind: "error" | "ok"; text: string }

export default function Notice({ state }: { state: NoticeState | null }) {
  if (!state) return null;
  return <div className={`notice ${state.kind}`}>{state.text}</div>;
}
