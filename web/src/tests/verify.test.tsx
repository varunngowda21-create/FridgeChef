import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { VerifyCandidates } from '@/features/scan/VerifyCandidates';

const mockScanData = {
  scan_id: 'scan-uuid-123',
  expires_at: '2026-10-28T22:30:00Z',
  image_quality: 'GOOD',
  image_quality_note: null,
  candidates: [
    {
      candidate_id: 'c1',
      name: 'Tomato',
      canonical_id: 'tomato',
      quantity: 4,
      unit: 'piece',
      storage_guess: 'FRIDGE',
      confidence: 'HIGH',
      needs_review: false,
      visible_note: 'Ripe red',
    },
    {
      candidate_id: 'c2',
      name: 'Milk',
      canonical_id: 'milk',
      quantity: 1,
      unit: 'packet',
      storage_guess: 'FRIDGE',
      confidence: 'MEDIUM',
      needs_review: false,
      visible_note: '',
    },
    {
      candidate_id: 'c3',
      name: 'Mystery Herb',
      canonical_id: null,
      quantity: 1,
      unit: 'bunch',
      storage_guess: 'FRIDGE',
      confidence: 'LOW',
      needs_review: true,
      visible_note: 'Hidden in corner',
    },
  ],
};

vi.mock('@/api/endpoints', () => ({
  endpoints: {
    getScan: vi.fn().mockImplementation(() => Promise.resolve(mockScanData)),
    confirmScan: vi.fn().mockResolvedValue({ created: [], skipped: [] }),
    discardScan: vi.fn().mockResolvedValue(undefined),
  },
}));

describe('Verify Candidates Screen', () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  it('pre-checks HIGH and MEDIUM confidence items and pre-unchecks LOW confidence items', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/scan/scan-uuid-123/verify']}>
          <Routes>
            <Route path="/scan/:scanId/verify" element={<VerifyCandidates />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(await screen.findByText('Tomato')).toBeInTheDocument();
    expect(screen.getByText('Milk')).toBeInTheDocument();
    expect(screen.getByText('Mystery Herb')).toBeInTheDocument();

    const tomatoCheckbox = screen.getByLabelText(/Select Tomato/i) as HTMLInputElement;
    const milkCheckbox = screen.getByLabelText(/Select Milk/i) as HTMLInputElement;
    const herbCheckbox = screen.getByLabelText(/Select Mystery Herb/i) as HTMLInputElement;

    // High and Medium are checked by default
    expect(tomatoCheckbox.checked).toBe(true);
    expect(milkCheckbox.checked).toBe(true);

    // Low confidence is pre-unchecked per PRD Section 6.3 & 12.3
    expect(herbCheckbox.checked).toBe(false);

    // Initial count is 2 of 3
    expect(screen.getByText(/2 of 3 items selected to add/i)).toBeInTheDocument();

    // User can manually check the low confidence item
    fireEvent.click(herbCheckbox);
    expect(herbCheckbox.checked).toBe(true);
    expect(screen.getByText(/3 of 3 items selected to add/i)).toBeInTheDocument();
  });
});

