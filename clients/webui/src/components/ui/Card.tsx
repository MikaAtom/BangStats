import type { ReactNode } from "react";

interface CardProps {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
}

export function Card({ title, children, actions, className }: CardProps) {
  return (
    <section className={`card ${className || ""}`}>
      <div className="card-header">
        <h3>{title}</h3>
        {actions}
      </div>
      {children}
    </section>
  );
}
