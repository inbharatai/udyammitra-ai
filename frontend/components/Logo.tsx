export default function Logo({ size = 36 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="UdyamMitra AI">
      <rect width="64" height="64" rx="14" fill="#003B73" />
      {/* upward growth arc forming a U */}
      <path d="M14 44 C14 22 50 22 50 44" stroke="#F7931E" strokeWidth="4.5" strokeLinecap="round" fill="none" />
      {/* growth arrow */}
      <path d="M32 14 L40 22 L34 22 L34 30 L30 30 L30 22 L24 22 Z" fill="#F7931E" />
      {/* handshake / mitra motif — two clasped chevrons */}
      <path d="M22 46 L32 52 L42 46" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" opacity="0.9" />
      <circle cx="32" cy="52" r="2.4" fill="#FFFFFF" />
    </svg>
  );
}