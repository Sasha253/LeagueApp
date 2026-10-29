// Add a club (docs/DECISIONS.md): a superuser names a new Club and its first Admin, by email.
// They're Admin at once if they have an account, else when they sign up. The API answers
// 403 to anyone else.

import { useState } from "react";
import { useNavigate } from "react-router";
import { api } from "../../api/client";
import { formErrors, unreachable, type FormErrors } from "../../api/errors";
import { Banner } from "../../components/Banner";
import { TextField } from "../../components/TextField";
import { ScreenHeader } from "../teams/shared";
import { NO_ERRORS } from "./shared";

export function AddClubPage() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [admin, setAdmin] = useState("");
  const [errors, setErrors] = useState<FormErrors>(NO_ERRORS);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    setErrors(NO_ERRORS);
    try {
      const { data, error, response } = await api.POST("/api/v1/clubs/", { body: { name, admin_email: admin } });
      if (data) navigate(`/clubs/${data.id}`);
      else if (response.status === 403) setErrors({ fields: {}, general: "Only a superuser can add a club." });
      else setErrors(formErrors(error));
    } catch {
      setErrors(unreachable);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="la-screen">
      <ScreenHeader title="Add a club" back={{ label: "All clubs", to: "/clubs" }} />
      <form
        className="la-stack la-form"
        aria-label="New club"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <TextField
          label="Club name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={errors.fields.name}
        />
        <TextField
          label="First Admin's email"
          type="email"
          value={admin}
          help="Admin at once if they have an account, otherwise when they sign up."
          onChange={(event) => setAdmin(event.target.value)}
          error={errors.fields.admin_email ?? errors.fields.email}
        />
        {errors.general && <Banner status="cancelled" title={errors.general} />}
        <button
          type="submit"
          className="la-btn la-btn--primary la-btn--block"
          disabled={busy || !name.trim() || !admin.trim()}
        >
          Add club
        </button>
      </form>
    </main>
  );
}
