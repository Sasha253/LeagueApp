// TextField (proposed component, docs/DECISIONS.md): label, input, help or error.

import { useId, type InputHTMLAttributes } from "react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "className"> & {
  label: string;
  help?: string;
  error?: string;
};

export function TextField({ label, help, error, ...input }: Props) {
  const id = useId();
  const noteId = `${id}-note`;
  const note = error ?? help;

  return (
    <div className="la-field">
      <label className="la-field__label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className={`la-input${error ? " la-input--error" : ""}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={note ? noteId : undefined}
        {...input}
      />
      {note && (
        <span id={noteId} className={error ? "la-field__error" : "la-field__help"}>
          {note}
        </span>
      )}
    </div>
  );
}
