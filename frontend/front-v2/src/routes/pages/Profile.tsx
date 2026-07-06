import { SignOut } from "@phosphor-icons/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

// F-07 placeholder — pełny profil (kronika/społeczność/ustawienia) w KROKU 2/8 (#1238).
export default function Profile() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <Avatar className="h-16 w-16">
          <AvatarFallback />
        </Avatar>
        <div>
          <h1 className="font-serif text-title-lg text-text">demo</h1>
          <p className="font-mono text-micro text-text-3">demo@ai-gm.local</p>
        </div>
      </div>

      <Tabs defaultValue="chronicle">
        <TabsList>
          <TabsTrigger value="chronicle">Kronika</TabsTrigger>
          <TabsTrigger value="social">Społeczność</TabsTrigger>
          <TabsTrigger value="settings">Ustawienia</TabsTrigger>
        </TabsList>
        <TabsContent value="chronicle">
          <Card>
            <CardHeader>
              <CardTitle>Kroniki bohaterów</CardTitle>
            </CardHeader>
            <CardContent>Wkrótce — legendy Twoich postaci.</CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="social">
          <Card>
            <CardHeader>
              <CardTitle>Znajomi i zaproszenia</CardTitle>
            </CardHeader>
            <CardContent>Wkrótce.</CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="settings">
          <Card>
            <CardHeader>
              <CardTitle>Ustawienia konta</CardTitle>
            </CardHeader>
            <CardContent>LLM · wygląd · bezpieczeństwo — wkrótce.</CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Button variant="danger" className="self-start">
        <SignOut size={18} /> Wyloguj
      </Button>
    </div>
  );
}
