import { useEffect, useRef, useState } from "react";
import creatorClip from "@/assets/creator-clip.mp4";
import creatorPoster from "@/assets/creator-hero.jpg";

const FALLBACK_SRC =
  "https://id-preview--9d2ccf3f-f0a1-4ee6-874c-e3427477334f.lovable.app/__l5e/assets-v1/dfe691cf-e0ce-43ed-8d6e-01f509e97a4e/creator-clip.mp4";

/** Phone-mockup video — forces play after mount (autoplay policies). */
export function HeroVideo({ className }: { className?: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [src, setSrc] = useState(creatorClip);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.muted = true;
    const play = () => {
      void el.play().catch(() => undefined);
    };
    play();
    el.addEventListener("canplay", play);
    return () => el.removeEventListener("canplay", play);
  }, [src]);

  return (
    <video
      ref={ref}
      className={className}
      src={src}
      poster={creatorPoster}
      autoPlay
      loop
      muted
      playsInline
      preload="auto"
      onError={() => {
        if (src !== FALLBACK_SRC) setSrc(FALLBACK_SRC);
      }}
    />
  );
}
