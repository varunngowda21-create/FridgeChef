import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ScanCamera } from '@/features/scan/ScanCamera';
import { VerifyCandidates } from '@/features/scan/VerifyCandidates';
import { endpoints } from '@/api/endpoints';

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    uploadScan: vi.fn(),
    getScan: vi.fn(),
    confirmScan: vi.fn(),
    discardScan: vi.fn(),
  },
}));

describe('Scan, Verification & Candidate Correction Flows', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();
  });

  it('rejects image files exceeding 8MB before attempting upload', async () => {
    render(
      <MemoryRouter>
        <ScanCamera />
      </MemoryRouter>
    );

    // Create simulated 9MB file
    const oversizedFile = new File(['x'.repeat(1024)], 'giant_fridge.jpg', {
      type: 'image/jpeg',
    });
    Object.defineProperty(oversizedFile, 'size', { value: 9 * 1024 * 1024 });

    const input = screen.getByLabelText(/take fridge photo/i);
    fireEvent.change(input, { target: { files: [oversizedFile] } });

    await waitFor(() => {
      expect(screen.getByText(/maximum allowed size is 8mb/i)).toBeInTheDocument();
      expect(endpoints.uploadScan).not.toHaveBeenCalled();
    });
  });

  it('allows candidate editing and inline correction of unmapped canonical ID', async () => {
    vi.mocked(endpoints.getScan).mockResolvedValueOnce({
      scan_id: 'scan-123',
      status: 'PENDING_VERIFY',
      expires_at: '2026-10-28T23:00:00Z',
      image_quality: 'GOOD',
      image_quality_note: null,
      candidates: [
        {
          candidate_id: 'cand-1',
          name: 'Green Veggie',
          canonical_id: '',
          quantity: 2,
          unit: 'piece',
          storage_guess: 'FRIDGE',
          confidence: 'MEDIUM',
          needs_review: true,
          visible_note: null,
        },
      ],
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/scan/scan-123/verify']}>
          <Routes>
            <Route path="/scan/:scanId/verify" element={<VerifyCandidates />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Green Veggie')).toBeInTheDocument();
    });

    // Open edit modal for Green Veggie
    fireEvent.click(screen.getByLabelText('Edit Green Veggie'));

    await waitFor(() => {
      expect(screen.getByText('Edit Green Veggie')).toBeInTheDocument();
    });

    // Change canonical id to capsicum
    const canonicalInput = screen.getByLabelText(/canonical ingredient id/i);
    fireEvent.change(canonicalInput, { target: { value: 'capsicum' } });

    fireEvent.click(screen.getByRole('button', { name: /done/i }));

    // Verify modal is closed
    await waitFor(() => {
      expect(screen.queryByText('Edit Green Veggie')).not.toBeInTheDocument();
    });
  });

  it('validates canonical ID before submitting scan confirmation', async () => {
    vi.mocked(endpoints.getScan).mockResolvedValueOnce({
      scan_id: 'scan-unmapped',
      status: 'PENDING_VERIFY',
      expires_at: '2026-10-28T23:00:00Z',
      image_quality: 'GOOD',
      image_quality_note: null,
      candidates: [
        {
          candidate_id: 'cand-unmapped',
          name: 'Mystery Herb',
          canonical_id: '',
          quantity: 1,
          unit: 'bunch',
          storage_guess: 'FRIDGE',
          confidence: 'MEDIUM',
          needs_review: true,
          visible_note: null,
        },
      ],
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/scan/scan-unmapped/verify']}>
          <Routes>
            <Route path="/scan/:scanId/verify" element={<VerifyCandidates />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Mystery Herb')).toBeInTheDocument();
    });

    // Attempt to confirm without canonical ID
    fireEvent.click(screen.getByRole('button', { name: /save \(1\) to fridge/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/requires a valid canonical ingredient id/i)
      ).toBeInTheDocument();
      expect(endpoints.confirmScan).not.toHaveBeenCalled();
    });
  });

  it('discards scan session and deletes image on user cancel', async () => {
    vi.mocked(endpoints.getScan).mockResolvedValueOnce({
      scan_id: 'scan-to-discard',
      status: 'PENDING_VERIFY',
      expires_at: '2026-10-28T23:00:00Z',
      image_quality: 'GOOD',
      image_quality_note: null,
      candidates: [],
    });
    vi.mocked(endpoints.discardScan).mockResolvedValueOnce(undefined);

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/scan/scan-to-discard/verify']}>
          <Routes>
            <Route path="/scan/:scanId/verify" element={<VerifyCandidates />} />
            <Route path="/" element={<div>Home Screen</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /discard scan/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /discard scan/i }));

    await waitFor(() => {
      expect(endpoints.discardScan).toHaveBeenCalledWith('scan-to-discard');
      expect(screen.getByText('Home Screen')).toBeInTheDocument();
    });
  });
});
