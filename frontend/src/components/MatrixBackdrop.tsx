import { useEffect, useRef } from "react";

const GLYPHS = "01ABCDEF0123456789{}[]<>/\\+-*#$%&";

/** Decorative, locally rendered glyph field. No external script, image or tracking. */
export default function MatrixBackdrop() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    let drops: number[] = [];
    let timer = 0;
    const fontSize = 16;

    function resize() {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas!.width = Math.floor(width * ratio);
      canvas!.height = Math.floor(height * ratio);
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      context!.setTransform(ratio, 0, 0, ratio, 0, 0);
      context!.fillStyle = "#090a09";
      context!.fillRect(0, 0, width, height);
      drops = Array.from({ length: Math.ceil(width / fontSize) }, () => Math.floor(Math.random() * -45));
    }

    function draw() {
      context!.fillStyle = "rgba(9, 10, 9, .13)";
      context!.fillRect(0, 0, width, height);
      context!.font = `13px "JetBrains Mono", monospace`;
      drops.forEach((drop, index) => {
        const glyph = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
        const x = index * fontSize;
        const y = drop * fontSize;
        context!.fillStyle = index % 7 === 0 ? "rgba(70,255,93,.52)" : "rgba(26,255,52,.25)";
        context!.fillText(glyph, x, y);
        if (y > height && Math.random() > 0.975) drops[index] = Math.floor(Math.random() * -20);
        else drops[index] += 1;
      });
    }

    resize();
    draw();
    if (!reducedMotion) timer = window.setInterval(draw, 85);
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); if (timer) window.clearInterval(timer); };
  }, []);
  return <canvas ref={canvasRef} className="matrix-backdrop" aria-hidden="true" />;
}
