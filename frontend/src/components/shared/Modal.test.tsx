/**
 * Modal lifecycle regression tests: every OpenMesh dialog must close on
 * Escape, on backdrop click, and via the X button — and must NOT close on
 * clicks inside the card. These are the bugs that previously required a
 * browser refresh.
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Modal from "./Modal";

afterEach(cleanup);

function renderModal(onClose = vi.fn()) {
  render(
    <Modal onClose={onClose} aria-label="test-modal">
      <button type="button">inside-button</button>
      <p>modal body</p>
    </Modal>,
  );
  return onClose;
}

describe("Modal lifecycle", () => {
  it("closes on Escape", () => {
    const onClose = renderModal();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on backdrop click", () => {
    const onClose = renderModal();
    const backdrop = screen.getByRole("dialog");
    fireEvent.mouseDown(backdrop);
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not close on clicks inside the card", () => {
    const onClose = renderModal();
    const inside = screen.getByText("inside-button");
    fireEvent.mouseDown(inside);
    fireEvent.click(inside);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("does not close when a drag starts inside and ends outside", () => {
    const onClose = renderModal();
    const inside = screen.getByText("modal body");
    const backdrop = screen.getByRole("dialog");
    fireEvent.mouseDown(inside); // e.g. selecting text in an input
    fireEvent.click(backdrop);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes via the X button", () => {
    const onClose = renderModal();
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("can hide the X button for confirmation dialogs", () => {
    render(
      <Modal onClose={vi.fn()} showClose={false} aria-label="confirm">
        <p>confirm body</p>
      </Modal>,
    );
    expect(screen.queryByLabelText("Close")).toBeNull();
  });

  it("removes the Escape listener on unmount", () => {
    const onClose = vi.fn();
    const { unmount } = render(
      <Modal onClose={onClose} aria-label="test-modal">
        <p>body</p>
      </Modal>,
    );
    unmount();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });
});
