import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ARTICLES } from "../content/articles";
import Articles from "./Articles";

describe("Articles page", () => {
  it("lists every article and filters by category using accessible tabs", async () => {
    render(<MemoryRouter><Articles /></MemoryRouter>);
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(ARTICLES.length);

    await userEvent.click(screen.getByRole("tab", { name: "Responsible AI" }));
    const expected = ARTICLES.filter((a) => a.category === "Responsible AI").length;
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(expected);
    expect(screen.getByRole("tab", { name: "Responsible AI" })).toHaveAttribute("aria-selected", "true");
  });
});
