export default function Skeleton({ height = 20, width }: { height?: number; width?: number | string }) {
  return <div className="skeleton" style={{ height, width: width ?? "100%" }} />;
}
