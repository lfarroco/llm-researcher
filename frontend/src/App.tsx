import { useState, useEffect } from 'react';
import { api } from './api/client';
import type { Research } from './types';
import ResearchForm from './components/ResearchForm';
import ResearchList from './components/ResearchList';
import ResearchDetail from './components/ResearchDetail';
import SettingsPage from './components/SettingsPage';

function App() {
	const [researches, setResearches] = useState<Research[]>([]);
	const [selectedResearch, setSelectedResearch] = useState<number | null>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [activeView, setActiveView] = useState<'research' | 'settings'>('research');
	const [showResearchForm, setShowResearchForm] = useState(false);

	// Filter state
	const [statusFilter, setStatusFilter] = useState<string>('');
	const [searchQuery, setSearchQuery] = useState<string>('');

	const loadResearches = async () => {
		try {
			setLoading(true);
			const filters: { status?: string; search?: string } = {};
			if (statusFilter) filters.status = statusFilter;
			if (searchQuery) filters.search = searchQuery;

			const data = await api.listResearch(0, 50, filters);
			setResearches(data);
			setError(null);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load researches');
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		loadResearches();
	}, [statusFilter, searchQuery]);

	useEffect(() => {
		// Poll for updates every 10 seconds (only if no active filters for performance)
		if (!statusFilter && !searchQuery) {
			const interval = setInterval(loadResearches, 10000);
			return () => clearInterval(interval);
		}
	}, [statusFilter, searchQuery]);

	const handleResearchCreated = (research: Research) => {
		setResearches([research, ...researches]);
		setSelectedResearch(research.id);
		setShowResearchForm(false);
	};

	const handleResearchDeleted = (id: number) => {
		setResearches(researches.filter(r => r.id !== id));
		if (selectedResearch === id) {
			setSelectedResearch(null);
		}
	};

	return (
		<div className="min-h-screen bg-gray-50">
			<header className="bg-white shadow-sm">
				<div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
					<div>
						<h1 className="text-2xl font-bold text-gray-900">🔬 LLM Researcher</h1>
						<p className="text-sm text-gray-600 mt-1">
							Autonomous AI-powered research assistant
						</p>
					</div>
					<nav className="flex items-center gap-2">
						<button
							onClick={() => setActiveView('research')}
							className={`px-3 py-2 text-sm rounded-md transition-colors ${activeView === 'research'
								? 'bg-blue-600 text-white'
								: 'bg-gray-100 text-gray-700 hover:bg-gray-200'
								}`}
						>
							Research
						</button>
						<button
							onClick={() => setActiveView('settings')}
							className={`px-3 py-2 text-sm rounded-md transition-colors ${activeView === 'settings'
								? 'bg-blue-600 text-white'
								: 'bg-gray-100 text-gray-700 hover:bg-gray-200'
								}`}
						>
							Settings
						</button>
					</nav>
				</div>
			</header>

			<main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
				{error && (
					<div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
						{error}
					</div>
				)}

				{activeView === 'settings' ? (
					<SettingsPage />
				) : (
					<>
						<div className="grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)] gap-6 items-start">
							<aside className="space-y-4 lg:sticky lg:top-6">
								<div className="bg-white rounded-lg shadow p-4">
									<button
										onClick={() => setShowResearchForm((prev) => !prev)}
										className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
									>
										{showResearchForm ? 'Close New Research' : 'New Research'}
									</button>
								</div>

								{showResearchForm && (
									<ResearchForm onResearchCreated={handleResearchCreated} />
								)}

								<ResearchList
									researches={researches}
									selectedId={selectedResearch}
									onSelect={setSelectedResearch}
									loading={loading}
									statusFilter={statusFilter}
									onStatusFilterChange={setStatusFilter}
									searchQuery={searchQuery}
									onSearchQueryChange={setSearchQuery}
								/>
							</aside>

							<section>
								{selectedResearch ? (
									<ResearchDetail
										researchId={selectedResearch}
										onDelete={handleResearchDeleted}
										onUpdate={loadResearches}
									/>
								) : (
									<div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
										<p className="text-lg">Select a research query to view details</p>
										<p className="text-sm mt-2">or start a new one from the sidebar</p>
									</div>
								)}
							</section>
						</div>
					</>
				)}
			</main>

			<footer className="mt-12 pb-6 text-center text-sm text-gray-500">
				<p>Built with FastAPI, LangChain, and React</p>
			</footer>
		</div>
	);
}

export default App;
