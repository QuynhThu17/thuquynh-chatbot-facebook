import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface BotCardProps {
  id: string;
  name: string;
  role: string;
  target: string;
  mission: string;
  note?: string;
  status?: string;
  type?: string;
}

export function BotCard({ id, name, role, target, mission, note, status, type }: BotCardProps) {
  const getStatusBadge = (status: string) => {
    const statusConfig = {
      on: { text: 'Đang hoạt động', className: 'bg-green-100 text-green-800' },
      off: { text: 'Không hoạt động', className: 'bg-red-100 text-red-800' },
    };
    
    const config = statusConfig[status as keyof typeof statusConfig] || { text: 'Không xác định', className: 'bg-gray-100 text-gray-800' };
    
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.className}`}>
        {config.text}
      </span>
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-lg">{name}</CardTitle>
        {status && getStatusBadge(status)}
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <p className="text-sm font-medium text-gray-600">Vai trò:</p>
          <p className="text-sm text-gray-800">{role}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-600">Mục tiêu:</p>
          <p className="text-sm text-gray-800">{target}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-600">Nhiệm vụ:</p>
          <p className="text-sm text-gray-800">{mission}</p>
        </div>
        {note && (
          <div>
            <p className="text-sm font-medium text-gray-600">Ghi chú:</p>
            <p className="text-sm text-gray-800">{note}</p>
          </div>
        )}
        {type && (
          <div>
            <p className="text-sm font-medium text-gray-600">Loại:</p>
            <p className="text-sm text-gray-800 capitalize">{type}</p>
          </div>
        )}
      </CardContent>
      <CardFooter className="flex justify-end space-x-2">
        <Button variant="outline" size="sm">Xem chi tiết</Button>
        <Button variant="outline" size="sm" className="text-blue-600 hover:text-blue-700">Chỉnh sửa</Button>
        <Button variant="destructive" size="sm">Xóa</Button>
      </CardFooter>
    </Card>
  );
}