import React, { useState, useEffect, useCallback } from 'react';
import type { PageId, HealthResponse } from './types';
import { fetchHealth } from './api/client';
import { Sidebar } from './components/Sidebar';
import { Topbar } from './components/Topbar';
import { DashboardPage } from './pages/DashboardPage';
import { SettingsPage } from './pages/SettingsPage';
import { CreateCasePage } from './pages/CreateCasePage';
import { MyCasesPage } from './pages/MyCasesPage';
import { CaseDetailPage } from './pages/CaseDetailPage';
import { EvidenceUploadPage } from './pages/EvidenceUploadPage';
import { EvidenceDetailPage } from './pages/EvidenceDetailPage';
import { IntegrityCheckPage } from './pages/IntegrityCheckPage';
import { AnalysisResultsPage } from './pages/AnalysisResultsPage';
import { CrossCheckPage } from './pages/CrossCheckPage';
import { ReportsPage } from './pages/ReportsPage';
import { AuditLogPage } from './pages/AuditLogPage';


export const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<PageId>('dashboard');
  const [selectedCaseId, setSelectedCaseId] = useState<string | number | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<number | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(false);

  const loadHealth = useCallback(async () => {
    setLoadingHealth(true);
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch (err) {
      console.warn('Backend health check diagnostic unreachable:', err);
      setHealth(null);
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  useEffect(() => {
    loadHealth();
    // Periodically poll health every 30 seconds
    const interval = setInterval(loadHealth, 30000);
    return () => clearInterval(interval);
  }, [loadHealth]);

  const handleNavigate = (page: PageId, caseIdentifier?: string | number, evidenceId?: number) => {
    if (caseIdentifier !== undefined) {
      setSelectedCaseId(caseIdentifier);
    }
    if (evidenceId !== undefined) {
      setSelectedEvidenceId(evidenceId);
    }
    setCurrentPage(page);
  };


  const renderContent = () => {
    switch (currentPage) {
      case 'dashboard':
        return <DashboardPage health={health} onNavigate={handleNavigate} />;

      case 'create-case':
        return <CreateCasePage onNavigate={handleNavigate} health={health} />;

      case 'my-cases':
        return <MyCasesPage onNavigate={handleNavigate} />;

      case 'case-details':
        return (
          <CaseDetailPage
            caseIdentifier={selectedCaseId}
            onNavigate={handleNavigate}
          />
        );

      case 'evidence-upload':
        return (
          <EvidenceUploadPage
            initialCaseId={selectedCaseId}
            onNavigate={handleNavigate}
          />
        );

      case 'evidence-details':
        return (
          <EvidenceDetailPage
            evidenceId={selectedEvidenceId}
            onNavigate={handleNavigate}
          />
        );

      case 'integrity-check':
        return <IntegrityCheckPage onNavigate={handleNavigate} />;


      case 'analysis-results':
        return (
          <AnalysisResultsPage
            initialEvidenceId={selectedEvidenceId}
            onNavigate={handleNavigate}
          />
        );


      case 'cross-check':
        return (
          <CrossCheckPage
            initialCaseId={selectedCaseId}
            onNavigate={handleNavigate}
          />
        );

      case 'reports':
        return (
          <ReportsPage
            initialCaseId={selectedCaseId}
            onNavigate={handleNavigate}
          />
        );

      case 'audit-log':
        return (
          <AuditLogPage
            onNavigate={handleNavigate}
          />
        );

      case 'settings':
        return <SettingsPage health={health} />;

      default:
        return <DashboardPage health={health} onNavigate={handleNavigate} />;
    }
  };

  return (
    <div className="app-container">
      <Sidebar currentPage={currentPage} onNavigate={handleNavigate} />
      <div className="main-wrapper">
        <Topbar
          currentPage={currentPage}
          health={health}
          loadingHealth={loadingHealth}
          onRefreshHealth={loadHealth}
        />
        <main className="content-area">{renderContent()}</main>
      </div>
    </div>
  );
};

export default App;
