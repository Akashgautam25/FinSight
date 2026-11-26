"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell, PasswordInput } from "@/components/layout/AuthShell";
import { apiError, authApi, tokens } from "@/lib/api";
import { passwordRule } from "@/lib/validation";

const schema = z
  .object({
    full_name: z.string().trim().min(2, "Name must be at least 2 characters"),
    email: z.string().trim().email("Enter a valid email address"),
    password: passwordRule,
    confirm_password: z.string(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type Form = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Auto-redirect if already signed in
  useEffect(() => {
    if (tokens.access) {
      router.replace("/overview");
    }
  }, [router]);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { full_name: "", email: "", password: "", confirm_password: "" },
  });

  const passwordValue = watch("password") || "";
  const confirmPasswordValue = watch("confirm_password") || "";

  // Password rules indicators
  const rules = [
    { label: "At least 8 characters", valid: passwordValue.length >= 8 },
    { label: "One uppercase letter (A-Z)", valid: /[A-Z]/.test(passwordValue) },
    { label: "One lowercase letter (a-z)", valid: /[a-z]/.test(passwordValue) },
    { label: "One number (0-9)", valid: /\d/.test(passwordValue) },
  ];

  const passwordsMatch =
    confirmPasswordValue.length > 0 && passwordValue === confirmPasswordValue;

  const onSubmit = async (data: Form) => {
    try {
      const res = await authApi.register({
        email: data.email.trim(),
        password: data.password,
        full_name: data.full_name.trim(),
      });
      tokens.set(res.data.access_token, res.data.refresh_token);
      queryClient.invalidateQueries({ queryKey: ["me"] });
      toast.success("Account created — your starter portfolio and watchlist are ready.");
      router.replace("/overview");
    } catch (error) {
      toast.error(apiError(error, "Registration failed. Please try again."));
    }
  };

  return (
    <AuthShell
      title="Create account"
      subtitle="Start your financial research journey"
      footer={
        <>
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="full_name">Full name</Label>
          <Input
            id="full_name"
            autoComplete="name"
            placeholder="Alex Johnson"
            disabled={isSubmitting}
            {...register("full_name")}
          />
          {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            disabled={isSubmitting}
            {...register("email")}
          />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            autoComplete="new-password"
            placeholder="Create a strong password"
            show={showPassword}
            onToggle={() => setShowPassword(!showPassword)}
            disabled={isSubmitting}
            {...register("password")}
          />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}

          {/* Dynamic Password Strength Indicators */}
          {passwordValue.length > 0 && (
            <div className="mt-2 space-y-1 rounded-md border border-border/50 bg-muted/20 p-2.5 text-[11px]">
              <p className="font-medium text-foreground">Password requirements:</p>
              <div className="grid grid-cols-1 gap-1 text-muted-foreground sm:grid-cols-2">
                {rules.map((rule, idx) => (
                  <div
                    key={idx}
                    className={`flex items-center gap-1.5 transition-colors ${
                      rule.valid ? "text-profit" : "text-muted-foreground"
                    }`}
                  >
                    {rule.valid ? (
                      <Check className="h-3 w-3 shrink-0" />
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50 shrink-0" />
                    )}
                    <span>{rule.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="confirm_password">Confirm password</Label>
            {confirmPasswordValue.length > 0 && (
              <span
                className={`flex items-center gap-1 text-[11px] font-medium ${
                  passwordsMatch ? "text-profit" : "text-destructive"
                }`}
              >
                {passwordsMatch ? (
                  <>
                    <Check className="h-3 w-3" /> Passwords match
                  </>
                ) : (
                  <>
                    <X className="h-3 w-3" /> Passwords do not match
                  </>
                )}
              </span>
            )}
          </div>
          <PasswordInput
            id="confirm_password"
            autoComplete="new-password"
            placeholder="Repeat your password"
            show={showConfirmPassword}
            onToggle={() => setShowConfirmPassword(!showConfirmPassword)}
            disabled={isSubmitting}
            {...register("confirm_password")}
          />
          {errors.confirm_password && (
            <p className="text-xs text-destructive">{errors.confirm_password.message}</p>
          )}
        </div>

        <Button type="submit" className="mt-2 w-full" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Creating account…
            </>
          ) : (
            "Create account"
          )}
        </Button>
      </form>
    </AuthShell>
  );
}
