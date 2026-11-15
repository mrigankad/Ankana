import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthApiError, type AuthConfig, type SessionPayload } from "@/lib/auth/api";

vi.mock("@/lib/auth/api", async (orig) => {
  const actual = await orig<typeof import("@/lib/auth/api")>();
  return {
    ...actual,
    authApi: {
      requestCode: vi.fn(),
      verifyCode: vi.fn(),
      passwordSignin: vi.fn(),
      signup: vi.fn(),
      createPractice: vi.fn(),
      oidcStartUrl: (p: string, next: string) => `http://api/v1/auth/oidc/${p}/start?redirect=${encodeURIComponent(next)}`,
    },
  };
});

import { authApi } from "@/lib/auth/api";
import { SignInForm } from "./sign-in-form";
import { SignUpForm } from "./sign-up-form";

const api = vi.mocked(authApi, true);

const CONFIG: AuthConfig = {
  email_code: true,
  phone_code: false,
  password: true,
  signup: true,
  oidc: [],
  password_min_length: 10,
  otp_ttl_seconds: 600,
};

const SESSION: SessionPayload = {
  access_token: "tok",
  expires_in: 900,
  session_id: "s1",
  user: { id: "u1", email: "a@b.in", name: "A", has_password: false },
  memberships: [],
  active_practice_id: null,
};

beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);

describe("SignInForm", () => {
  it("asks for an email, then the code, then signs in", async () => {
    api.requestCode.mockResolvedValue({ ok: true, expires_in: 600 });
    api.verifyCode.mockResolvedValue(SESSION);
    const onSession = vi.fn();
    render(<SignInForm config={CONFIG} next="/clients" onSession={onSession} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.in" } });
    fireEvent.click(screen.getByRole("button", { name: /email me a code/i }));
    await screen.findByLabelText(/six digit code/i);
    expect(api.requestCode).toHaveBeenCalledWith("a@b.in");

    const signIn = screen.getByRole("button", { name: "Sign in" });
    expect(signIn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/six digit code/i), { target: { value: "12ab34 56" } });
    expect(screen.getByLabelText(/six digit code/i)).toHaveValue("123456");
    fireEvent.click(signIn);
    await waitFor(() => expect(onSession).toHaveBeenCalledWith(SESSION));
    expect(api.verifyCode).toHaveBeenCalledWith("a@b.in", "123456");
  });

  it("shows the server's message when the code is wrong", async () => {
    api.requestCode.mockResolvedValue({ ok: true, expires_in: 600 });
    api.verifyCode.mockRejectedValue(new AuthApiError(400, "invalid_code", "That code is wrong or has expired."));
    render(<SignInForm config={CONFIG} next="/" onSession={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.in" } });
    fireEvent.click(screen.getByRole("button", { name: /email me a code/i }));
    fireEvent.change(await screen.findByLabelText(/six digit code/i), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("wrong or has expired");
  });

  it("signs in with a password on the password tab", async () => {
    api.passwordSignin.mockResolvedValue(SESSION);
    const onSession = vi.fn();
    render(<SignInForm config={CONFIG} next="/" onSession={onSession} />);
    fireEvent.click(screen.getByRole("tab", { name: "Password" }));
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.in" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(onSession).toHaveBeenCalled());
    expect(api.passwordSignin).toHaveBeenCalledWith("a@b.in", "correct horse battery");
  });

  it("hides the password tab and provider buttons unless configured", () => {
    render(<SignInForm config={{ ...CONFIG, password: false }} next="/" onSession={vi.fn()} />);
    expect(screen.queryByRole("tab", { name: "Password" })).toBeNull();
    expect(screen.queryByText(/sign in with/i)).toBeNull();
  });

  it("renders one button per configured provider, carrying the return path", () => {
    render(
      <SignInForm
        config={{ ...CONFIG, oidc: [{ id: "keycloak", label: "Keycloak" }, { id: "google", label: "Google" }] }}
        next="/clients"
        onSession={vi.fn()}
      />,
    );
    const link = screen.getByRole("link", { name: /sign in with keycloak/i });
    expect(link).toHaveAttribute("href", "http://api/v1/auth/oidc/keycloak/start?redirect=%2Fclients");
    expect(screen.getByRole("link", { name: /sign in with google/i })).toBeInTheDocument();
  });

  it("explains a failed provider redirect", () => {
    render(<SignInForm config={CONFIG} next="/" redirectError="oidc_email_unverified" onSession={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("verified email");
  });
});

describe("SignUpForm", () => {
  it("collects name, practice and email, then confirms the code", async () => {
    api.signup.mockResolvedValue({ ok: true, expires_in: 600 });
    api.verifyCode.mockResolvedValue({ ...SESSION });
    const onSession = vi.fn();
    render(<SignUpForm onSession={onSession} />);
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: " Asha Rao " } });
    fireEvent.change(screen.getByLabelText("Practice name"), { target: { value: "Asha Jyotish" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "asha@x.in" } });
    fireEvent.click(screen.getByRole("button", { name: /email me a code/i }));
    await screen.findByLabelText(/six digit code/i);
    expect(api.signup).toHaveBeenCalledWith({ email: "asha@x.in", name: "Asha Rao", practice_name: "Asha Jyotish" });
    fireEvent.change(screen.getByLabelText(/six digit code/i), { target: { value: "654321" } });
    fireEvent.click(screen.getByRole("button", { name: /create my practice/i }));
    await waitFor(() => expect(onSession).toHaveBeenCalled());
    expect(api.verifyCode).toHaveBeenCalledWith("asha@x.in", "654321");
  });

  it("for an invite asks no practice name and locks the invited email", async () => {
    api.signup.mockResolvedValue({ ok: true, expires_in: 600 });
    render(<SignUpForm withPractice={false} presetEmail="mate@x.in" onSession={vi.fn()} />);
    expect(screen.queryByLabelText("Practice name")).toBeNull();
    expect(screen.getByLabelText("Email")).toHaveAttribute("readonly");
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "Mate" } });
    fireEvent.click(screen.getByRole("button", { name: /email me a code/i }));
    await screen.findByLabelText(/six digit code/i);
    expect(api.signup).toHaveBeenCalledWith({ email: "mate@x.in", name: "Mate" });
  });

  it("surfaces rate limit errors", async () => {
    api.signup.mockRejectedValue(new AuthApiError(429, "rate_limited", "Too many codes requested."));
    render(<SignUpForm onSession={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "A" } });
    fireEvent.change(screen.getByLabelText("Practice name"), { target: { value: "P" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@x.in" } });
    fireEvent.click(screen.getByRole("button", { name: /email me a code/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Too many codes");
  });
});
