// Sign up, one field per step (design/src/ds/Screens.md, Shared 1). The backend checks
// everything again; a step only needs an answer before Next.

import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { api, type Position } from "../api/client";
import { formErrors, unreachable, type FormErrors } from "../api/errors";
import { useAuth } from "../auth/AuthProvider";
import { Banner } from "../components/Banner";
import { ChoiceChip } from "../components/ChoiceChip";
import { TextField } from "../components/TextField";
import { POSITIONS } from "./positions";

type Step = "email" | "name" | "phone" | "password" | "roles" | "position";

type Answers = {
  email: string;
  name: string;
  phone: string;
  password: string;
  plays: boolean;
  books: boolean;
  position: Position | null;
};

const NO_ERRORS: FormErrors = { fields: {}, general: null };

/** Which step shows the server's error for a field. */
const STEP_OF_FIELD: Record<string, Step> = {
  email: "email",
  name: "name",
  phone: "phone",
  password: "password",
  "player.position": "position",
};

export function SignUpPage() {
  const { state, startSession } = useAuth();
  const navigate = useNavigate();
  const [answers, setAnswers] = useState<Answers>({
    email: "",
    name: "",
    phone: "",
    password: "",
    plays: true,
    books: false,
    position: null,
  });
  const [step, setStep] = useState<Step>("email");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  if (state.status === "signedIn") return <Navigate to="/profile" replace />;

  const steps: Step[] = ["email", "name", "phone", "password", "roles"];
  if (answers.plays) steps.push("position");
  const index = steps.indexOf(step);
  const isLast = index === steps.length - 1;

  const answer = <K extends keyof Answers>(key: K, value: Answers[K]) =>
    setAnswers((current) => ({ ...current, [key]: value }));

  const answered: Record<Step, boolean> = {
    email: answers.email.trim() !== "",
    name: answers.name.trim() !== "",
    phone: true,
    password: answers.password !== "",
    roles: answers.plays || answers.books,
    position: answers.position !== null,
  };

  async function register() {
    setBusy(true);
    setErrors(NO_ERRORS);
    try {
      const { data, error } = await api.POST("/api/v1/auth/register/", {
        body: {
          email: answers.email.trim(),
          name: answers.name.trim(),
          phone: answers.phone.trim(),
          password: answers.password,
          is_booking_user: answers.books,
          player: answers.plays && answers.position ? { position: answers.position } : null,
        },
      });
      if (data) {
        await startSession({ access: data.access, refresh: data.refresh }, data.user);
        navigate("/profile", { replace: true });
        return;
      }
      const found = formErrors(error);
      setErrors(found);
      const failed = steps.find((s) => Object.keys(found.fields).some((f) => STEP_OF_FIELD[f] === s));
      if (failed) setStep(failed);
    } catch {
      setErrors(unreachable);
    } finally {
      setBusy(false);
    }
  }

  function next(event: FormEvent) {
    event.preventDefault();
    if (!answered[step]) return;
    if (isLast) void register();
    else setStep(steps[index + 1] ?? step);
  }

  const fieldError = (field: string) => errors.fields[field];

  return (
    <main className="la-screen">
      <div className="la-stack-2">
        <p className="la-overline">
          Step {index + 1} of {steps.length}
        </p>
        <h1 className="title-1">Sign up</h1>
      </div>
      <form className="la-stack" onSubmit={next} noValidate>
        {errors.general && <Banner status="cancelled" title={errors.general} />}

        {step === "email" && (
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            inputMode="email"
            autoFocus
            value={answers.email}
            onChange={(e) => answer("email", e.target.value)}
            error={fieldError("email")}
          />
        )}
        {step === "name" && (
          <TextField
            label="Your name"
            autoComplete="name"
            autoFocus
            value={answers.name}
            onChange={(e) => answer("name", e.target.value)}
            error={fieldError("name")}
          />
        )}
        {step === "phone" && (
          <TextField
            label="Phone"
            type="tel"
            autoComplete="tel"
            inputMode="tel"
            autoFocus
            help="Optional. So your Captain or the club can reach you."
            value={answers.phone}
            onChange={(e) => answer("phone", e.target.value)}
            error={fieldError("phone")}
          />
        )}
        {step === "password" && (
          <TextField
            label="Password"
            type="password"
            autoComplete="new-password"
            autoFocus
            help="At least 8 characters, not only numbers."
            value={answers.password}
            onChange={(e) => answer("password", e.target.value)}
            error={fieldError("password")}
          />
        )}
        {step === "roles" && (
          <fieldset className="la-fieldset la-stack-2">
            <legend className="headline">How will you use League App?</legend>
            <p className="caption la-muted">Choose one or both.</p>
            <div className="la-choices">
              <ChoiceChip pressed={answers.plays} onToggle={() => answer("plays", !answers.plays)}>
                I play
              </ChoiceChip>
              <ChoiceChip pressed={answers.books} onToggle={() => answer("books", !answers.books)}>
                I hire a field
              </ChoiceChip>
            </div>
          </fieldset>
        )}
        {step === "position" && (
          <fieldset className="la-fieldset la-stack-2">
            <legend className="headline">Where do you play?</legend>
            <div className="la-choices">
              {POSITIONS.map(({ value, label }) => (
                <ChoiceChip
                  key={value}
                  pressed={answers.position === value}
                  onToggle={() => answer("position", value)}
                >
                  {label}
                </ChoiceChip>
              ))}
            </div>
            {fieldError("player.position") && (
              <span className="la-field__error">{fieldError("player.position")}</span>
            )}
          </fieldset>
        )}

        <div className="la-actions">
          <button
            type="button"
            className="la-btn la-btn--secondary"
            disabled={index === 0 || busy}
            onClick={() => setStep(steps[index - 1] ?? step)}
          >
            Back
          </button>
          <button type="submit" className="la-btn la-btn--primary" disabled={!answered[step] || busy}>
            {isLast ? "Create account" : "Next"}
          </button>
        </div>
      </form>
      <p className="body la-muted">
        Have an account?{" "}
        <Link className="la-btn la-btn--quiet" to="/login">
          Log in
        </Link>
      </p>
    </main>
  );
}
