export type WorkspaceGroup = "OVERVIEW" | "GROWTH" | "INTELLIGENCE" | "SYSTEM";

export type WorkspaceModule = {
  id: string;
  number: string;
  label: string;
  href: string;
  group: WorkspaceGroup;
  description: string;
};

export const WORKSPACE_MODULES: WorkspaceModule[] = [
  {id: "dashboard", number: "01", label: "Tổng quan", href: "/dashboard", group: "OVERVIEW", description: "Trung tâm điều hành"},
  {id: "pao-ai", number: "02", label: "PAO AI", href: "/pao-ai", group: "OVERVIEW", description: "Bộ não điều phối PAO"},
  {id: "tasks", number: "03", label: "Công việc và dự án", href: "/tasks", group: "OVERVIEW", description: "Công việc của con người và trợ lý AI"},
  {id: "meta-ads", number: "04", label: "Meta Ads", href: "/meta-ads", group: "GROWTH", description: "Phân tích quảng cáo Meta"},
  {id: "tiktok-ads", number: "05", label: "TikTok Ads", href: "/tiktok-ads", group: "GROWTH", description: "Hiệu quả quảng cáo TikTok"},
  {id: "google-ads", number: "06", label: "Google Ads", href: "/google-ads", group: "GROWTH", description: "Phân tích quảng cáo Google"},
  {id: "crm", number: "07", label: "CRM", href: "/crm", group: "GROWTH", description: "Khách hàng và doanh thu"},
  {id: "content-creative", number: "08", label: "Nội dung và sáng tạo", href: "/content-creative", group: "GROWTH", description: "Điều phối nội dung sáng tạo"},
  {id: "analytics", number: "09", label: "Phân tích", href: "/analytics", group: "INTELLIGENCE", description: "Nguồn dữ liệu đối chiếu thống nhất"},
  {id: "automation", number: "10", label: "Tự động hóa", href: "/automation", group: "INTELLIGENCE", description: "Trung tâm quy trình và trợ lý"},
  {id: "knowledge", number: "11", label: "Kho tri thức", href: "/knowledge", group: "INTELLIGENCE", description: "Bộ nhớ doanh nghiệp dài hạn"},
  {id: "settings", number: "12", label: "Cài đặt và kết nối", href: "/settings", group: "SYSTEM", description: "Trung tâm điều khiển"},
];

export const WORKSPACE_GROUPS: WorkspaceGroup[] = ["OVERVIEW", "GROWTH", "INTELLIGENCE", "SYSTEM"];


// Existing URLs remain stable; secondary tools belong to a primary customer area.
export const WORKSPACE_SUBVIEWS = [
  {parent:'tasks',href:'/business-planning',label:'Kế hoạch kinh doanh',requiresPlanning:true},
  {parent:'automation',href:'/automation/goals',label:'Thực hiện mục tiêu',requiresPlanning:false},
  {parent:'automation',href:'/automation/review',label:'Kết quả và phê duyệt',requiresPlanning:false},
  {parent:'automation',href:'/channels',label:'Hộp thư và kênh',requiresPlanning:false},
];
