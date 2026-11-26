"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell, PasswordInput } from "@/components/layout/AuthShell";
import { apiError, authApi, tokens } from "@/lib/api";

const schema = z.object({
  email: z.string().trim().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});
type Form = z.infer<typeof schema>;

const DEMO = { email: "demo@finsight.ai", password: "FinSight2026!" };

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const [show, setShow] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);

  // Auto-redirect if already signed in
  useEffect(() => {
    if (tokens.access) {
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/overview");
    }
  }, [params, router]);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const handleSuccessfulAuth = (accessToken: string, refreshToken: string) => {
    tokens.set(accessToken, refreshToken);
    queryClient.invalidateQueries({ queryKey: ["me"] });
    toast.success("Welcome back!");
    const next = params.get("next");
    const target = next && next.startsWith("/") && !next.startsWith("//") ? next : "/overview";
    router.replace(target);
  };

  const onSubmit = async (data: Form) => {
    try {
      const res = await authApi.login(data.email.trim(), data.password);
      handleSuccessfulAuth(res.data.access_token, res.data.refresh_token);
    } catch (error) {
      toast.error(apiError(error, "Invalid email or password"));
    }
  };

  const onInstantDemoLogin = async () => {
    setValue("email", DEMO.email, { shouldValidate: true });
    setValue("password", DEMO.password, { shouldValidate: true });
    setDemoLoading(true);
    try {
      const res = await authApi.login(DEMO.email, DEMO.password);
      handleSuccessfulAuth(res.data.access_token, res.data.refresh_token);
    } catch (error) {
      toast.error(apiError(error, "Demo account not seeded yet. Run make seed in backend."));
    } finally {
      setDemoLoading(false);
    }
  };

  return (
    <AuthShell
      title="Sign in"
      subtitle="Access your financial intelligence dashboard"
      footer={
        <>
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-medium text-primary hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            disabled={isSubmitting || demoLoading}
            {...register("email")}
          />
          {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link href="/forgot-password" className="text-xs text-primary hover:underline">
              Forgot password?
            </Link>
          </div>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            placeholder="••••••••"
            show={show}
            onToggle={() => setShow(!show)}
            disabled={isSubmitting || demoLoading}
            {...register("password")}
          />
          {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
        </div>

        <Button type="submit" className="w-full" disabled={isSubmitting || demoLoading}>
          {isSubmitting ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Signing in…
            </>
          ) : (
            "Sign in"
          )}
        </Button>
      </form>

      {/* Demo Account Box */}
      <div className="mt-5 rounded-lg border border-dashed border-border/80 bg-muted/20 p-3.5 text-xs text-muted-foreground">
        <div className="mb-2 flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-medium text-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary" /> Demo Account
          </span>
          <span className="font-mono text-[11px] text-muted-foreground">Pre-configured</span>
        </div>
        <p className="leading-relaxed">
          Quickly explore without creating a new user. Log in with{" "}
          <span className="font-mono font-medium text-foreground">{DEMO.email}</span>.
        </p>
        <div className="mt-3 flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="flex-1 text-xs"
            disabled={isSubmitting || demoLoading}
            onClick={() => {
              setValue("email", DEMO.email, { shouldValidate: true });
              setValue("password", DEMO.password, { shouldValidate: true });
              toast.info("Demo credentials filled.");
            }}
          >
            Fill credentials
          </Button>
          <Button
            type="button"
            size="sm"
            className="flex-1 gap-1 text-xs"
            disabled={isSubmitting || demoLoading}
            onClick={onInstantDemoLogin}
          >
            {demoLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <>
                Demo Sign-in <ArrowRight className="h-3 w-3" />
              </>
            )}
          </Button>
        </div>
      </div>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
