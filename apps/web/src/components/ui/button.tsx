import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#6366f1] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0f] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-[#6366f1] text-white shadow-lg shadow-[#6366f1]/20 hover:bg-[#818cf8] hover:shadow-[#6366f1]/30",
        primary:
          "bg-[#6366f1] text-white shadow-lg shadow-[#6366f1]/20 hover:bg-[#818cf8] hover:shadow-[#6366f1]/30",
        destructive:
          "bg-[#ef4444] text-white shadow hover:bg-[#ef4444]/90",
        outline:
          "border border-[#1e1e2e] bg-transparent text-[#ededed] hover:bg-[#12121a] hover:border-[#2a2a40]",
        secondary:
          "bg-[#12121a] text-[#ededed] border border-[#1e1e2e] hover:bg-[#1e1e2e]",
        ghost: "text-[#9ca3af] hover:text-[#ededed] hover:bg-[#12121a]",
        link: "text-[#6366f1] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-lg px-8 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
