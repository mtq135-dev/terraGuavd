import { ReactNode } from "react";

export function Panel({
  title,
  children,
  action,
  className = "",
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Empty({
  children = "No records available.",
}: {
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span aria-hidden>◇</span>
      <p>{children}</p>
    </div>
  );
}
export function Metric({
  title,
  value,
  icon,
  tone = "blue",
}: {
  title: string;
  value: string | number;
  icon: string;
  tone?: string;
}) {
  return (
    <section className="metric">
      <span className={`metric-icon ${tone}`} aria-hidden>
        {icon}
      </span>
      <div>
        <span>{title}</span>
        <strong>{value}</strong>
        <small>Simulation workspace</small>
      </div>
    </section>
  );
}
