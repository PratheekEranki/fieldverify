export function Loading({ text = 'Loading…' }: { text?: string }) {
  return <p className="muted">{text}</p>
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <p className="note note-red" role="alert">
      {message}
    </p>
  )
}
