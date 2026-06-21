export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return 'just now';
  const time = new Date(iso).getTime();
  if (Number.isNaN(time)) return 'just now';
  const deltaMs = Date.now() - time;
  const mins = Math.max(0, Math.floor(deltaMs / 60000));
  if (mins < 1) return 'just now';
  if (mins === 1) return '1 min ago';
  if (mins < 60) return `${mins} mins ago`;
  const hours = Math.floor(mins / 60);
  if (hours === 1) return '1 hour ago';
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? '1 day ago' : `${days} days ago`;
}

export function formatAbsoluteTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const time = new Date(iso);
  if (Number.isNaN(time.getTime())) return '—';
  return time.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

