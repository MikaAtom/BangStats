import type { ReactNode } from "react";

interface CardProps {
  title: ReactNode;
  children: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function Card({ title, subtitle, children, actions, className }: CardProps) {
  return (
    <section className={`card ${className || ""}`}>
      <div className="card-header">
        <div className="card-heading">
          <h3>{title}</h3>
          {subtitle ? <div className="card-subtitle">{subtitle}</div> : null}
        </div>
        {actions ? <div className="card-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
