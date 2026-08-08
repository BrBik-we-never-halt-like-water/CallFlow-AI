'use client';

import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/cn';
import { supabaseBrowser } from '@/lib/supabase/client';

const MAX_BYTES = 2 * 1024 * 1024;
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

export interface ImageUploadProps {
  /** Matches the storage bucket's RLS policy - see the migration in Part 3. */
  bucket: 'avatars' | 'org-logos';
  /** The org or user id the bucket policy checks the upload path against. */
  ownerId: string;
  value: string | null;
  onChange: (url: string) => void;
  label: string;
  shape?: 'circle' | 'square';
}

/**
 * Upload straight to Supabase Storage from the browser - no API round trip for the
 * bytes themselves, just the resulting public URL, which the caller persists.
 */
export function ImageUpload({
  bucket,
  ownerId,
  value,
  onChange,
  label,
  shape = 'circle',
}: ImageUploadProps) {
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  async function handleFile(file: File) {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      toast({ tone: 'error', title: 'Use a JPG, PNG, or WEBP image.' });
      return;
    }
    if (file.size > MAX_BYTES) {
      toast({
        tone: 'error',
        title: 'Image is too large',
        body: 'Keep it under 2MB.',
      });
      return;
    }

    setUploading(true);
    try {
      const extension = file.name.split('.').pop()?.toLowerCase() || 'png';
      const path = `${ownerId}/${Date.now()}.${extension}`;
      const { error } = await supabaseBrowser()
        .storage.from(bucket)
        .upload(path, file, { upsert: true, cacheControl: '3600' });
      if (error) throw error;

      const { data } = supabaseBrowser()
        .storage.from(bucket)
        .getPublicUrl(path);
      onChange(data.publicUrl);
    } catch {
      toast({
        tone: 'error',
        title: 'Upload failed',
        body: 'Try a different image.',
      });
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="flex items-center gap-4">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        aria-label={label}
        className={cn(
          'flex size-16 shrink-0 items-center justify-center overflow-hidden border border-rule bg-surface-sunken text-text-dim transition-colors hover:bg-surface-hover',
          shape === 'circle' ? 'rounded-full' : 'rounded-lg',
        )}
      >
        {value ? (
          // eslint-disable-next-line @next/next/no-img-element -- a remote Supabase Storage URL, not an app asset
          <img src={value} alt="" className="size-full object-cover" />
        ) : (
          <span aria-hidden className="text-h3">
            +
          </span>
        )}
      </button>

      <div className="flex flex-col gap-1.5">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={uploading}
          onClick={() => inputRef.current?.click()}
        >
          {value ? 'Change image' : 'Upload image'}
        </Button>
        <span className="text-small text-text-dim">
          JPG, PNG, or WEBP - up to 2MB.
        </span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
          e.target.value = '';
        }}
      />
    </div>
  );
}
