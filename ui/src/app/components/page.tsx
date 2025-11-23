import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function ComponentsShowcase() {
  return (
    <div className="flex min-h-screen w-full items-start justify-center bg-background p-6">
      <main className="w-full max-w-2xl space-y-6">
        <Card className="bg-card text-card-foreground">
          <CardHeader>
            <CardTitle>Buttons</CardTitle>
            <CardDescription>Kiểm tra các biến thể của Button</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Button>Default</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="link">Link</Button>
            <Button size="sm">Small</Button>
            <Button size="lg">Large</Button>
            <Button size="icon" aria-label="Icon button">★</Button>
          </CardContent>
          <CardFooter className="text-muted-foreground">
            Tất cả Buttons hiển thị đúng màu và trạng thái.
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Input</CardTitle>
            <CardDescription>Trường nhập liệu cơ bản</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input placeholder="Nhập nội dung..." />
            <Input placeholder="Disabled" disabled />
          </CardContent>
          <CardFooter className="text-muted-foreground">
            Kiểm tra focus ring, border và placeholder.
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Card</CardTitle>
            <CardDescription>Card với header, content và footer</CardDescription>
          </CardHeader>
          <CardContent>
            Nội dung card minh họa.
          </CardContent>
          <CardFooter>
            <Button>Hành động</Button>
          </CardFooter>
        </Card>
      </main>
    </div>
  );
}