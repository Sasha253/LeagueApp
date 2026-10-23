import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { api } from "../api/client";
import { formErrors, unreachable, type FormErrors } from "../api/errors";
import { useAuth } from "../auth/AuthProvider";
import { Banner } from "../components/Banner";
import { TextField } from "../components/TextField";

const NO_ERRORS: FormErrors = { fields: {}, general: null };

export function LoginPage() {
  const { state, startSession } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  if (state.status === "signedIn") return <Navigate to="/profile" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setErrors(NO_ERRORS);
    try {
      const login = await api.POST("/api/v1/auth/login/", {
        body: { email, password },
      });
      if (!login.data) {
        setErrors(
          login.response.status === 401
            ? { fields: {}, general: "That email and password don't match an account." }
            : formErrors(login.error),
        );
        return;
      }
      const tokens = { access: login.data.access, refresh: login.data.refresh };
      const me = await api.GET("/api/v1/auth/me/", {
        headers: { Authorization: `Bearer ${tokens.access}` },
      });
      if (!me.data) return setErrors(formErrors(me.error));
      await startSession(tokens, me.data);
      navigate("/profile", { replace: true });
    } catch {
      setErrors(unreachable);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="la-screen">
      <h1 className="title-1">Log in</h1>
      <form className="la-stack" onSubmit={submit} noValidate>
        {errors.general && <Banner status="cancelled" title={errors.general} />}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          inputMode="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.fields.email}
          required
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.fields.password}
          required
        />
        <button
          type="submit"
          className="la-btn la-btn--primary la-btn--block"
          disabled={busy || !email || !password}
        >
          Log in
        </button>
      </form>
      <p className="body la-muted">
        New here?{" "}
        <Link className="la-btn la-btn--quiet" to="/signup">
          Sign up
        </Link>
      </p>
    </main>
  );
}
