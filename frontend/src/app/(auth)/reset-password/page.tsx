"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell, PasswordInput } from "@/components/layout/AuthShell";
import { apiError, authApi } from "@/lib/api";
import { passwordRule } from "@/lib/validation";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const check = passwordRule.safeParse(password);
    if (!check.success) return toast.error(check.error.issues[0].message);
    if (password !== confirm) return toast.error("Passwords do not match");
    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      toast.success("Password updated — please sign in.");
      router.replace("/login");
    } catch (error) {
      toast.error(apiError(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Choose a new password" subtitle="Reset links are valid for 30 minutes and can be used once."
      footer={<Link href="/login" className="text-primary hover:underline">Back to sign in</Link>}>
      {!token ? (
        <p className="text-sm text-destructive">This reset link is missing its token. Request a new link from the <Link href="/forgot-password" className="underline">forgot password</Link> page.</p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="password">New password</Label>
            <PasswordInput id="password" value={password} onChange={(e) => setPassword(e.target.value)} show={show} onToggle={() => setShow(!show)} placeholder="8+ chars, upper, lower, digit" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirm password</Label>
            <Input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Update password"}</Button>
        </form>
      )}
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
