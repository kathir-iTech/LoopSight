import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#38bdf8] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a1628] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-[#38bdf8] text-[#0a1628] shadow-lg shadow-[#38bdf8]/20 hover:bg-[#0ea5e9] hover:shadow-[#38bdf8]/30 font-semibold",
        primary:
          "bg-[#38bdf8] text-[#0a1628] shadow-lg shadow-[#38bdf8]/20 hover:bg-[#0ea5e9] hover:shadow-[#38bdf8]/30 font-semibold",
        destructive:
          "bg-[#ef4444] text-white shadow hover:bg-[#ef4444]/90",
        outline:
          "border border-[#1e3a5f] bg-transparent text-[#e6f0ff] hover:bg-[#0f2942] hover:border-[#234b7a]",
        secondary:
          "bg-[#0f2942] text-[#e6f0ff] border border-[#1e3a5f] hover:bg-[#12365a]",
        ghost: "text-[#8aa0c0] hover:text-[#e6f0ff] hover:bg-[#0f2942]",
        link: "text-[#38bdf8] underline-offset-4 hover:underline",
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
