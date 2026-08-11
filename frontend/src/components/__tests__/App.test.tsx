import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../../App';

// Mock the API client to prevent real HTTP calls
vi.mock('../../api/client', () => ({
	api: {
		listResearch: vi.fn().mockResolvedValue([]),
	},
}));

describe('App', () => {
	it('renders the header "LLM Researcher"', () => {
		render(
			<MemoryRouter initialEntries={['/']}>
				<App />
			</MemoryRouter>
		);

		expect(screen.getByText('🔬 LLM Researcher')).toBeInTheDocument();
	});

	it('renders the subheader text', () => {
		render(
			<MemoryRouter initialEntries={['/']}>
				<App />
			</MemoryRouter>
		);

		expect(
			screen.getByText('Autonomous AI-powered research assistant')
		).toBeInTheDocument();
	});

	it('renders navigation tabs', () => {
		render(
			<MemoryRouter initialEntries={['/']}>
				<App />
			</MemoryRouter>
		);

		// "Research" appears both in the nav tab and as a table heading;
		// use getAllByText and confirm at least one is present.
		const researchElements = screen.getAllByText('Research');
		expect(researchElements.length).toBeGreaterThanOrEqual(1);

		// "Settings" only appears in the nav tab
		expect(screen.getByText('Settings')).toBeInTheDocument();
	});

	it('renders the "New Research" button on the home route', () => {
		render(
			<MemoryRouter initialEntries={['/']}>
				<App />
			</MemoryRouter>
		);

		expect(screen.getByText('New Research')).toBeInTheDocument();
	});
});
