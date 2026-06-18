import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";

import { AuthProvider, useAuth } from "./contexts/AuthContext";

// REQ-DASH-004 클라이언트 캐싱 (TTL: 예측 5분·추세 1시간·챌린지 5분 등 — 각 query에서 staleTime 지정)
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 기본 5분
    },
  },
});

import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { EmailVerifyPage } from "./pages/EmailVerifyPage";
import { MyPage } from "./pages/MyPage";
import { OCRUploadPage } from "./pages/OCRUploadPage";
import { OCRResultPage } from "./pages/OCRResultPage";
import { ManualInputPage } from "./pages/ManualInputPage";
import { LifestyleSurveyPage } from "./pages/LifestyleSurveyPage";
import { DietSurveyPage } from "./pages/DietSurveyPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ChallengeMainPage } from "./pages/ChallengeMainPage";
import { LabRecordPage } from "./pages/LabRecordPage";
import { AppointmentCalendarPage } from "./pages/AppointmentCalendarPage";
import { DailyCheckinPage } from "./pages/DailyCheckinPage";
import { EggHatchingPage } from "./pages/EggHatchingPage";
import { SlumpPage } from "./pages/SlumpPage";
import { LLMActionGuidePage } from "./pages/LLMActionGuidePage";
import { NotificationSettingsPage } from "./pages/NotificationSettingsPage";
import { NotificationListPage } from "./pages/NotificationListPage";
import { DailyQuizPage } from "./pages/DailyQuizPage";
import { SocialGroupPage } from "./pages/SocialGroupPage";
import { FamilyCheerPage } from "./pages/FamilyCheerPage";
import { DiningModePage } from "./pages/DiningModePage";
import { RAGChatbotPage } from "./pages/RAGChatbotPage";
import { SimulationPage } from "./pages/SimulationPage";
import { CheckupHistoryPage } from "./pages/CheckupHistoryPage";
import { CheckupManagementPage } from "./pages/CheckupManagementPage";
import { CheckupInputMethodPage } from "./pages/CheckupInputMethodPage";
import { LifestyleSurveyHistoryPage } from "./pages/LifestyleSurveyHistoryPage";
import { LifestyleManagementPage } from "./pages/LifestyleManagementPage";
import { EmergencyGuardPage } from "./pages/EmergencyGuardPage";
import { ShopPage } from "./pages/ShopPage";
import { PointHistoryPage } from "./pages/PointHistoryPage";
import { CollectionPage } from "./pages/CollectionPage";
import { RestModePage } from "./pages/RestModePage";
import { FAQPage } from "./pages/FAQPage";
import { AboutPage } from "./pages/AboutPage";
import { AdminLayout } from "./components/AdminLayout";
import { AdminOverviewPage } from "./pages/admin/AdminOverviewPage";
import { AdminUsersPage } from "./pages/admin/AdminUsersPage";
import { AdminUserDetailPage } from "./pages/admin/AdminUserDetailPage";
import { AdminChallengesPage } from "./pages/admin/AdminChallengesPage";
import { AdminLogsPage } from "./pages/admin/AdminLogsPage";
import { AdminSafetyPage } from "./pages/admin/AdminSafetyPage";
import { DisclaimerFooter } from "./components/DisclaimerFooter";
import { BottomTabBar } from "./components/BottomTabBar";
import { ImpersonationBanner } from "./components/ImpersonationBanner";

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token, isLoading } = useAuth();
  if (isLoading) return <div className="flex min-h-screen items-center justify-center text-text-secondary">로딩 중...</div>;
  return token ? <>{children}</> : <Navigate to="/" replace />;
}

function AppRoutes() {
  return (
    <Routes>
      {/* 공개 라우트 */}
      <Route path="/" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/email-verify" element={<EmailVerifyPage />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/faq" element={<FAQPage />} />

      {/* 인증 필요 라우트 */}
      <Route path="/dashboard" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
      <Route path="/mypage" element={<PrivateRoute><MyPage /></PrivateRoute>} />
      <Route path="/ocr-upload" element={<PrivateRoute><OCRUploadPage /></PrivateRoute>} />
      <Route path="/ocr-result" element={<PrivateRoute><OCRResultPage /></PrivateRoute>} />
      <Route path="/manual-input" element={<PrivateRoute><ManualInputPage /></PrivateRoute>} />
      <Route path="/lifestyle-survey" element={<PrivateRoute><LifestyleSurveyPage /></PrivateRoute>} />
      <Route path="/diet-survey" element={<PrivateRoute><DietSurveyPage /></PrivateRoute>} />
      <Route path="/challenge" element={<PrivateRoute><ChallengeMainPage /></PrivateRoute>} />
      <Route path="/challenge-ckd" element={<PrivateRoute><ChallengeMainPage /></PrivateRoute>} />
      <Route path="/records/lab" element={<PrivateRoute><LabRecordPage /></PrivateRoute>} />
      <Route path="/records/appointments" element={<PrivateRoute><AppointmentCalendarPage /></PrivateRoute>} />
      <Route path="/daily-checkin" element={<PrivateRoute><DailyCheckinPage /></PrivateRoute>} />
      <Route path="/egg-hatching" element={<PrivateRoute><EggHatchingPage /></PrivateRoute>} />
      <Route path="/slump" element={<PrivateRoute><SlumpPage /></PrivateRoute>} />
      <Route path="/llm-guide" element={<PrivateRoute><LLMActionGuidePage /></PrivateRoute>} />
      <Route path="/notification-settings" element={<PrivateRoute><NotificationSettingsPage /></PrivateRoute>} />
      <Route path="/notifications" element={<PrivateRoute><NotificationListPage /></PrivateRoute>} />
      <Route path="/daily-quiz" element={<PrivateRoute><DailyQuizPage /></PrivateRoute>} />
      <Route path="/social-group" element={<PrivateRoute><SocialGroupPage /></PrivateRoute>} />
      <Route path="/family-cheer" element={<PrivateRoute><FamilyCheerPage /></PrivateRoute>} />
      <Route path="/dining-mode" element={<PrivateRoute><DiningModePage /></PrivateRoute>} />
      <Route path="/rag-chatbot" element={<PrivateRoute><RAGChatbotPage /></PrivateRoute>} />
      <Route path="/simulation" element={<PrivateRoute><SimulationPage /></PrivateRoute>} />
      <Route path="/checkup-management" element={<PrivateRoute><CheckupManagementPage /></PrivateRoute>} />
      <Route path="/checkup-input" element={<PrivateRoute><CheckupInputMethodPage /></PrivateRoute>} />
      <Route path="/lifestyle-management" element={<PrivateRoute><LifestyleManagementPage /></PrivateRoute>} />
      <Route path="/checkup-history" element={<PrivateRoute><CheckupHistoryPage /></PrivateRoute>} />
      <Route path="/health-check-history" element={<PrivateRoute><CheckupHistoryPage /></PrivateRoute>} />
      <Route path="/lifestyle-survey-history" element={<PrivateRoute><LifestyleSurveyHistoryPage /></PrivateRoute>} />
      <Route path="/emergency" element={<PrivateRoute><EmergencyGuardPage /></PrivateRoute>} />
      <Route path="/shop" element={<PrivateRoute><ShopPage /></PrivateRoute>} />
      <Route path="/points/transactions" element={<PrivateRoute><PointHistoryPage /></PrivateRoute>} />
      <Route path="/collection" element={<PrivateRoute><CollectionPage /></PrivateRoute>} />
      <Route path="/rest-mode" element={<PrivateRoute><RestModePage /></PrivateRoute>} />

      {/* 관리자 페이지 — AdminLayout 내부에서 is_admin 가드 (false → /dashboard 리다이렉트) */}
      <Route path="/admin" element={<PrivateRoute><AdminLayout /></PrivateRoute>}>
        <Route index element={<AdminOverviewPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="users/:id" element={<AdminUserDetailPage />} />
        <Route path="challenges" element={<AdminChallengesPage />} />
        <Route path="safety" element={<AdminSafetyPage />} />
        <Route path="logs" element={<AdminLogsPage />} />
      </Route>
    </Routes>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <ImpersonationBanner />
          <AppRoutes />
          <DisclaimerFooter />
          <BottomTabBar />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
