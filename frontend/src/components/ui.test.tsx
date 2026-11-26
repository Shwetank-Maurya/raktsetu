import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Bar, Countdown, ErrorBox, Freshness, SevBadge, Stat } from "./ui";

describe("ui components", () => {
  it("SevBadge conveys severity in text, not colour alone", () => {
    render(<SevBadge sev="critical" />);
    expect(screen.getByText("critical")).toBeInTheDocument();
  });

  it("Bar exposes its value to assistive technology", () => {
    render(<Bar value={0.42} />);
    const meter = screen.getByRole("meter");
    expect(meter).toHaveAttribute("aria-valuenow", "42");
    expect(meter).toHaveAttribute("aria-valuemax", "100");
  });

  it("ErrorBox announces errors and renders nothing without one", () => {
    const { container, rerender } = render(<ErrorBox error={null} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ErrorBox error={new Error("Something failed")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Something failed");
  });

  it("Freshness labels stale facilities", () => {
    render(<Freshness hours={50} />);
    expect(screen.getByText("stale 50h")).toBeInTheDocument();
  });

  it("Countdown formats hours as HH:MM:SS with an accessible label", () => {
    render(<Countdown hours={1.5} asOf={new Date().toISOString()} />);
    expect(screen.getByLabelText(/1 hours 29 minutes|1 hours 30 minutes/)).toHaveTextContent(/^01:(29|30):\d\d$/);
  });

  it("Stat renders label and value", () => {
    render(<Stat label="Open alerts" value={12} />);
    expect(screen.getByText("Open alerts")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });
});
