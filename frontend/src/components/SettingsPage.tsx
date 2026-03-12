import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { AppSetting } from '../types';

const LABELS: Record<string, string> = {
	openai_api_key: 'OpenAI API Key',
	groq_api_key: 'Groq API Key',
	tavily_api_key: 'Tavily API Key',
	semantic_scholar_api_key: 'Semantic Scholar API Key',
	springer_api_key: 'Springer API Key',
	elsevier_api_key: 'Elsevier API Key',
	ncbi_api_key: 'NCBI API Key',
	ncbi_email: 'NCBI Email',
	app_env: 'App Environment',
	llm_provider: 'LLM Provider',
	llm_model: 'LLM Model',
	llm_temperature: 'LLM Temperature',
	ollama_base_url: 'Ollama Base URL',
	research_max_sources: 'Research Max Sources',
	research_timeout: 'Research Timeout (sec)',
	research_relevance_threshold: 'Research Relevance Threshold',
	research_enable_relevance_filter: 'Enable Relevance Filter',
	research_enable_query_expansion: 'Enable Query Expansion',
	research_query_variations: 'Research Query Variations',
	research_reference_chase_enabled: 'Enable Reference Chasing',
	research_reference_chase_depth: 'Reference Chase Depth',
	llm_max_retries: 'LLM Max Retries',
	llm_max_concurrent_requests: 'LLM Max Concurrent Requests',
	llm_retry_min_wait: 'LLM Retry Min Wait (sec)',
	llm_retry_max_wait: 'LLM Retry Max Wait (sec)',
	llm_base_delay: 'LLM Base Delay (sec)',
};

function toInputString(value: string | number | boolean): string {
	if (typeof value === 'boolean') return value ? 'true' : 'false';
	return String(value);
}

export default function SettingsPage() {
	const [settings, setSettings] = useState<AppSetting[]>([]);
	const [draftValues, setDraftValues] = useState<Record<string, string | boolean>>({});
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);
	const [savingKey, setSavingKey] = useState<string | null>(null);

	const settingsByKey = useMemo(() => {
		const map: Record<string, AppSetting> = {};
		for (const setting of settings) map[setting.key] = setting;
		return map;
	}, [settings]);

	const loadSettings = async () => {
		try {
			setLoading(true);
			setError(null);
			const data = await api.listSettings();
			setSettings(data);
			setDraftValues(
				Object.fromEntries(
					data.map((setting) => [
						setting.key,
						typeof setting.value === 'boolean'
							? setting.value
							: toInputString(setting.value),
					])
				),
			);
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to load settings');
		} finally {
			setLoading(false);
		}
	};

	useEffect(() => {
		loadSettings();
	}, []);

	const parseValue = (setting: AppSetting, draftValue: string | boolean): string | number | boolean => {
		if (setting.type === 'boolean') return Boolean(draftValue);
		if (setting.type === 'integer') return Number.parseInt(String(draftValue), 10);
		if (setting.type === 'number') return Number.parseFloat(String(draftValue));
		return String(draftValue);
	};

	const saveSetting = async (settingKey: string) => {
		const setting = settingsByKey[settingKey];
		if (!setting) return;

		try {
			setSavingKey(settingKey);
			setError(null);
			const parsed = parseValue(setting, draftValues[settingKey]);
			await api.updateSetting(settingKey, parsed);
			await loadSettings();
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to save setting');
		} finally {
			setSavingKey(null);
		}
	};

	const resetSetting = async (settingKey: string) => {
		try {
			setSavingKey(settingKey);
			setError(null);
			await api.clearSettingOverride(settingKey);
			await loadSettings();
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Failed to reset setting');
		} finally {
			setSavingKey(null);
		}
	};

	if (loading) {
		return (
			<div className="bg-white rounded-lg shadow p-6 text-gray-600">Loading settings...</div>
		);
	}

	return (
		<div className="bg-white rounded-lg shadow p-6">
			<div className="mb-6">
				<h2 className="text-xl font-semibold text-gray-900">Settings</h2>
				<p className="text-sm text-gray-600 mt-1">
					Values come from .env by default. Any value you save here is stored in the DB and takes precedence.
				</p>
			</div>

			{error && (
				<div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
					{error}
				</div>
			)}

			<div className="space-y-4">
				{settings.map((setting) => {
					const value = draftValues[setting.key];
					const isSaving = savingKey === setting.key;
					const label = LABELS[setting.key] || setting.key;

					return (
						<div key={setting.key} className="border border-gray-200 rounded-lg p-4">
							<div className="flex items-center justify-between gap-4 mb-3">
								<div>
									<h3 className="text-sm font-semibold text-gray-900">{label}</h3>
									<p className="text-xs text-gray-500">{setting.key}</p>
								</div>
								<span className={`text-xs px-2 py-1 rounded-full ${setting.source === 'db' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}>
									{setting.source === 'db' ? 'DB Override' : 'From .env'}
								</span>
							</div>

							{setting.type === 'boolean' ? (
								<label className="inline-flex items-center gap-2 text-sm text-gray-700">
									<input
										type="checkbox"
										checked={Boolean(value)}
										onChange={(e) => setDraftValues((prev) => ({ ...prev, [setting.key]: e.target.checked }))}
										disabled={isSaving}
									/>
									Enabled
								</label>
							) : (
								<input
									type={setting.sensitive ? 'password' : setting.type === 'string' ? 'text' : 'number'}
									step={setting.type === 'number' ? 'any' : undefined}
									value={String(value ?? '')}
									onChange={(e) => setDraftValues((prev) => ({ ...prev, [setting.key]: e.target.value }))}
									className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
									disabled={isSaving}
								/>
							)}

							<div className="mt-3 flex items-center gap-2">
								<button
									onClick={() => saveSetting(setting.key)}
									disabled={isSaving}
									className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:bg-gray-300"
								>
									{isSaving ? 'Saving...' : 'Save'}
								</button>
								<button
									onClick={() => resetSetting(setting.key)}
									disabled={isSaving || setting.source !== 'db'}
									className="px-3 py-1.5 bg-gray-100 text-gray-700 text-sm rounded-md hover:bg-gray-200 disabled:opacity-50"
								>
									Use .env Value
								</button>
							</div>
						</div>
					);
				})}
			</div>
		</div>
	);
}
