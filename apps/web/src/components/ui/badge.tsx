import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-[#38bdf8] focus:ring-offset-2 focus:ring-offset-[#0a1628]",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[#38bdf8] text-[#0a1628]",
        secondary:
          "border-transparent bg-[#1e3a5f] text-[#8aa0c0]",
        destructive:
          "border-transparent bg-[#ef4444] text-white",
        outline: "border-[#1e3a5f] text-[#8aa0c0]",
        success:
          "border-transparent bg-[#22c55e]/15 text-[#22c55e] border-[#22c55e]/30",
        warning:
          "border-transparent bg-[#f59e0b]/15 text-[#f59e0b] border-[#f59e0b]/30",
        info:
          "border-transparent bg-[#38bdf8]/15 text-[#38bdf8] border-[#38bdf8]/30",
        uncertain:
          "border-transparent bg-[#f59e0b]/15 text-[#f59e0b] border-[#f59e0b]/30",
        pass:
          "border-transparent bg-[#22c55e]/15 text-[#22c55e] border-[#22c55e]/30",
        fail:
          "border-transparent bg-[#ef4444]/15 text-[#ef4444] border-[#ef4444]/30",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
