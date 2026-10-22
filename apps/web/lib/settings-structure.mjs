export const settingsGroups=[
 {id:'general',label:'Tổng quan',description:'Tóm tắt và hướng dẫn bắt đầu'},
 {id:'organization',label:'Doanh nghiệp và nhãn hàng',description:'Quản lý tổ chức đang chọn'},
 {id:'team',label:'Tài khoản và nhân sự',description:'Thành viên, lời mời và truy cập'},
 {id:'integrations',label:'Kết nối',description:'Quảng cáo, BOT, ứng dụng và MCP'},
 {id:'ai',label:'AI và giọng nói',description:'Kết nối một lần, chọn AI mặc định'},
 {id:'safety',label:'An toàn và dữ liệu',description:'Chốt an toàn, hạn mức, xuất/xóa'},
 {id:'system',label:'Hệ thống và năng lực',description:'Trạng thái và thông tin kỹ thuật'},
];
export const settingsSections={
 organization:[{id:'enterprise',label:'Doanh nghiệp'},{id:'brands',label:'Nhãn hàng'}],
 team:[{id:'account',label:'Tài khoản của tôi'},{id:'members',label:'Thành viên'},{id:'invitations',label:'Lời mời'},{id:'permissions',label:'Quyền truy cập'}],
 ai:[{id:'providers',label:'Kết nối AI'},{id:'access',label:'AI mặc định'},{id:'voice',label:'Giọng nói'}],
 safety:[{id:'policy',label:'Chốt an toàn và phê duyệt'},{id:'quota',label:'Hạn mức'},{id:'exports',label:'Xuất dữ liệu'},{id:'deletions',label:'Yêu cầu xóa'}],
 system:[{id:'status',label:'Trạng thái hệ thống'},{id:'capabilities',label:'Năng lực PAO'}],
};
export function settingsSection(group,value){const items=Object.hasOwn(settingsSections,group)?settingsSections[group]:[];return items.some(x=>x.id===value)?value:items[0]?.id||''}
