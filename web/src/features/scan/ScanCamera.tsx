import React, { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { endpoints } from '@/api/endpoints';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { Camera, Image as ImageIcon, AlertCircle, Loader2, Sparkles } from 'lucide-react';

export const ScanCamera: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);

  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPreview, setSelectedPreview] = useState<string | null>(null);

  const handleFileSelected = async (file: File) => {
    setError(null);

    // Validate size (max 8MB per PRD Section 6.3 & 13.3)
    const maxBytes = 8 * 1024 * 1024;
    if (file.size > maxBytes) {
      setError('Image is too large. Maximum allowed size is 8MB.');
      return;
    }

    // Set preview
    const previewUrl = URL.createObjectURL(file);
    setSelectedPreview(previewUrl);

    setIsProcessing(true);
    try {
      const res = await endpoints.uploadScan(file);
      navigate(`/scan/${res.scan_id}/verify`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not process image. Please try again or add items manually.';
      setError(message);
      setIsProcessing(false);
    }
  };

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelected(e.target.files[0]);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-gray-900 tracking-tight">Scan Fridge or Pantry</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Take a clear photo to auto-detect ingredients and track shelf life.
        </p>
      </div>

      {error && (
        <div
          className="p-3.5 rounded-2xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2.5"
          role="alert"
        >
          <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">Scan Error</p>
            <p className="mt-0.5">{error}</p>
            <button
              onClick={() => navigate('/inventory')}
              className="mt-2 text-xs font-bold text-brand-700 underline"
            >
              Add items manually instead
            </button>
          </div>
        </div>
      )}

      {/* Progress state during upload and AI vision (NFR-002) */}
      {isProcessing ? (
        <Card className="text-center py-12 px-6 bg-brand-50/50 border-brand-200">
          <div className="relative w-20 h-20 mx-auto mb-4">
            {selectedPreview && (
              <img
                src={selectedPreview}
                alt="Uploaded fridge"
                className="w-full h-full object-cover rounded-2xl opacity-40"
              />
            )}
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="w-10 h-10 text-brand-600 animate-spin" />
            </div>
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-1">Looking at your fridge…</h3>
          <p className="text-xs text-gray-500 max-w-xs mx-auto">
            Our AI vision model is identifying groceries, estimating shelf-life, and matching regional ingredients.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Native camera file input (PRD Section 12.4) */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={onInputChange}
            accept="image/*"
            capture="environment"
            className="hidden"
            aria-label="Take fridge photo"
          />

          {/* Standard photo library file input */}
          <input
            type="file"
            ref={galleryInputRef}
            onChange={onInputChange}
            accept="image/jpeg,image/png,image/webp,image/heic"
            className="hidden"
            aria-label="Upload photo from library"
          />

          <Card
            onClick={() => fileInputRef.current?.click()}
            className="p-8 text-center border-2 border-dashed border-brand-300 bg-brand-50/30 hover:bg-brand-50 transition-colors cursor-pointer group"
          >
            <div className="w-16 h-16 rounded-3xl bg-brand-600 text-white flex items-center justify-center mx-auto mb-3 shadow-md group-hover:scale-105 transition-transform">
              <Camera className="w-8 h-8" />
            </div>
            <h3 className="text-base font-bold text-gray-900">Take a Photo</h3>
            <p className="text-xs text-gray-500 mt-1">Open camera to capture shelves, crisper, or counter</p>
          </Card>

          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-xs text-gray-400 font-medium">or</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          <Button
            variant="outline"
            size="lg"
            onClick={() => galleryInputRef.current?.click()}
            className="w-full font-semibold"
            icon={<ImageIcon className="w-5 h-5 text-gray-500" />}
          >
            Choose from Photo Gallery
          </Button>

          {/* Tips for best results */}
          <Card className="p-4 bg-gray-50 border-gray-200">
            <div className="flex items-start gap-2.5">
              <Sparkles className="w-4 h-4 text-brand-600 shrink-0 mt-0.5" />
              <div className="text-xs text-gray-600 leading-relaxed">
                <span className="font-semibold text-gray-800">Tips for accurate scans:</span> Ensure good lighting, open crisper drawers, and keep labels visible. You can review and adjust everything before saving!
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

