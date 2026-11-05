/** Error raised for any failed orchestrator call (HTTP or mock). status 0 = network failure. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.status ? `${err.status} · ${err.message}` : err.message;
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}
