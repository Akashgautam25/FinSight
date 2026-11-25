// AI Research Assistant page
"use client";

import { useState, useRef, useEffect } from "react";
import { useForm } from "react-hook-form";
import { motion, AnimatePresence } from "framer-motion";
import { aiApi } from "@/lib/api";
import { Send, Bot, User, Loader2, ExternalLink, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: any[];
  timestamp: Date;
}

const SUGGESTION_QUERIES = [
  "What is the current P/E ratio of AAPL?",
  "Compare NVDA and AMD performance over the past year",
  "Explain RSI and what it means for TSLA",
  "Summarize the latest financial news about MSFT",
  "What are the major risk metrics I should know?",
];

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { register, handleSubmit, reset, watch } = useForm<{ message: string }>();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async ({ message }: { message: string }) => {
    if (!message.trim() || isLoading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: message,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    reset();
    setIsLoading(true);

    try {
      const response = await aiApi.chat(message, sessionId || undefined);
      const data = response.data;

      setSessionId(data.session_id);

      const assistantMsg: Message = {
        id: data.message_id,
        role: "assistant",
        content: data.content,
        sources: data.sources,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (error: any) {
      toast.error("Failed to get response. Check your API configuration.");
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: "assistant",
          content: "I'm unable to process this request right now. Please ensure the backend is running and AI API keys are configured.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-h-[calc(100vh-10rem)]">
      <div className="mb-4">
        <h1 className="text-2xl font-bold tracking-tight">AI Research Assistant</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Ask anything about stocks, portfolios, or markets. Gets verified data before answering.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto rounded-xl border border-border/40 bg-card p-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center gap-6">
            <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
              <Bot className="h-7 w-7 text-primary" />
            </div>
            <div className="text-center">
              <h3 className="font-semibold mb-1">FinSight AI Assistant</h3>
              <p className="text-sm text-muted-foreground max-w-sm">
                Ask me about stocks, financial metrics, news, or your portfolio.
                I retrieve verified data before answering — I don&apos;t invent prices.
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 w-full max-w-lg">
              {SUGGESTION_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage({ message: q })}
                  className="text-left text-xs p-3 rounded-lg border border-border/40 hover:border-primary/40 hover:bg-primary/5 transition-all duration-150 text-muted-foreground hover:text-foreground"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  {msg.role === "assistant" && (
                    <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
                      <Bot className="h-4 w-4 text-primary" />
                    </div>
                  )}
                  <div
                    className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted/40 text-foreground"
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-border/20 space-y-1">
                        <p className="text-xs opacity-60 font-medium">Verified sources:</p>
                        {msg.sources.map((source: any, i: number) => (
                          <div key={i} className="flex items-center gap-1.5 text-xs opacity-70">
                            <span className="w-1.5 h-1.5 rounded-full bg-profit shrink-0" />
                            <span>{source.title}</span>
                            {source.url && (
                              <a href={source.url} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    <p className="text-xs opacity-40 mt-2">
                      {msg.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                  {msg.role === "user" && (
                    <div className="w-7 h-7 rounded-lg bg-muted flex items-center justify-center shrink-0 mt-0.5">
                      <User className="h-4 w-4 text-muted-foreground" />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            {isLoading && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                <div className="bg-muted/40 rounded-xl px-4 py-3">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Disclaimer */}
      <div className="flex items-center gap-2 my-2 px-1">
        <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />
        <p className="text-xs text-muted-foreground">
          AI responses use verified data where available. Always independently verify before making financial decisions.
        </p>
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit(sendMessage)} className="flex gap-2">
        <Input
          {...register("message", { required: true })}
          placeholder="Ask about stocks, portfolios, news, or financial metrics..."
          className="flex-1"
          disabled={isLoading}
        />
        <Button type="submit" size="icon" disabled={isLoading || !watch("message")?.trim()}>
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </form>
    </div>
  );
}
