import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

interface RouteErrorBoundaryProps {
  children: ReactNode;
  resetKey: string;
}

interface RouteErrorBoundaryState {
  error?: Error;
  resetKey: string;
}

export default class RouteErrorBoundary extends Component<RouteErrorBoundaryProps, RouteErrorBoundaryState> {
  state: RouteErrorBoundaryState = { resetKey: this.props.resetKey };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  static getDerivedStateFromProps(props: RouteErrorBoundaryProps, state: RouteErrorBoundaryState) {
    if (props.resetKey !== state.resetKey) {
      return { error: undefined, resetKey: props.resetKey };
    }
    return null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("OpenMesh route render failed", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="om-page">
        <div className="om-page-compact">
          <div className="om-alert-recovery">
            <AlertTriangle size={28} className="text-[color:var(--om-amber-500)]" />
            <div>
              <div className="om-kicker">Render Fault</div>
              <h1 className="mt-2 text-2xl font-bold text-[color:var(--om-text)]">This station failed to render</h1>
              <p className="mt-2 text-sm leading-6 text-[color:var(--om-muted)]">
                OpenMesh kept the shell alive. Try navigating to another station or reload this view.
              </p>
              <pre className="mt-4 max-h-32 overflow-auto rounded-[4px] border border-[color:var(--om-border)] bg-black/45 p-3 text-xs text-[color:var(--om-steel-300)]">
                {this.state.error.message}
              </pre>
              <button type="button" className="om-button mt-4" onClick={() => this.setState({ error: undefined })}>
                <RotateCcw size={14} /> Recover view
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
