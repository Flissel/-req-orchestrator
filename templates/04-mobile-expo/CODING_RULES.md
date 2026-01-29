# {{PROJECT_NAME}} - Coding Rules

## Expo Mobile App Implementierungsrichtlinien

---

## 1. Projekt-Architektur

### 1.1 Feature-basierte Struktur
```
app/
├── (tabs)/              # Tab-basierte Navigation
├── (auth)/              # Auth-Flow (Login, Register)
├── (modal)/             # Modal-Screens
└── [...unmatched].tsx   # 404 Handler

components/
├── ui/                  # Basis UI-Komponenten
├── forms/               # Form-Komponenten
└── features/            # Feature-spezifische Komponenten
```

### 1.2 Datei-Benennungen

| Typ | Convention | Beispiel |
|-----|-----------|----------|
| Screens | kebab-case | `app/user-profile.tsx` |
| Components | PascalCase | `Button.tsx` |
| Hooks | camelCase + use | `useAuth.ts` |
| Utils | camelCase | `formatDate.ts` |

---

## 2. Component Patterns

### 2.1 Screen Component

```typescript
// app/(tabs)/index.tsx
import { View, Text, StyleSheet } from 'react-native';
import { useLocalSearchParams } from 'expo-router';

export default function HomeScreen() {
  // Hooks am Anfang
  const params = useLocalSearchParams();
  
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Home</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
  },
});
```

### 2.2 Reusable Component

```typescript
// components/ui/Button.tsx
import { Pressable, Text, StyleSheet, ViewStyle } from 'react-native';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
  style?: ViewStyle;
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled = false,
  style,
}: ButtonProps) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        styles[variant],
        pressed && styles.pressed,
        disabled && styles.disabled,
        style,
      ]}
    >
      <Text style={[styles.text, styles[`${variant}Text`]]}>
        {title}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
  },
  primary: {
    backgroundColor: '#007AFF',
  },
  secondary: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#007AFF',
  },
  pressed: {
    opacity: 0.8,
  },
  disabled: {
    opacity: 0.5,
  },
  text: {
    fontSize: 16,
    fontWeight: '600',
  },
  primaryText: {
    color: 'white',
  },
  secondaryText: {
    color: '#007AFF',
  },
});
```

---

## 3. State Management

### 3.1 Zustand Store

```typescript
// lib/stores/authStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,
      
      login: async (email, password) => {
        set({ isLoading: true });
        try {
          const response = await api.login(email, password);
          set({ user: response.user, token: response.token });
        } finally {
          set({ isLoading: false });
        }
      },
      
      logout: () => {
        set({ user: null, token: null });
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => AsyncStorage),
    }
  )
);
```

### 3.2 React Query für API

```typescript
// hooks/useItems.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';

export function useItems() {
  return useQuery({
    queryKey: ['items'],
    queryFn: () => api.getItems(),
  });
}

export function useCreateItem() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreateItemData) => api.createItem(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
    },
  });
}
```

---

## 4. Navigation

### 4.1 Tab Navigation

```typescript
// app/(tabs)/_layout.tsx
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: '#007AFF',
        headerShown: false,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profil',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
```

### 4.2 Navigation Actions

```typescript
// In Components:
import { router } from 'expo-router';

// Navigate
router.push('/details/123');

// Replace
router.replace('/home');

// Back
router.back();

// Mit Params
router.push({
  pathname: '/user/[id]',
  params: { id: '123' },
});
```

---

## 5. Native APIs

### 5.1 Permissions

```typescript
// hooks/useCamera.ts
import { Camera } from 'expo-camera';
import { useState, useEffect } from 'react';

export function useCamera() {
  const [permission, requestPermission] = Camera.useCameraPermissions();
  
  const takePicture = async (cameraRef: Camera) => {
    if (!permission?.granted) {
      const result = await requestPermission();
      if (!result.granted) return null;
    }
    
    const photo = await cameraRef.takePictureAsync();
    return photo;
  };
  
  return { permission, requestPermission, takePicture };
}
```

### 5.2 Secure Storage

```typescript
// lib/secureStorage.ts
import * as SecureStore from 'expo-secure-store';

export const secureStorage = {
  async set(key: string, value: string): Promise<void> {
    await SecureStore.setItemAsync(key, value);
  },
  
  async get(key: string): Promise<string | null> {
    return SecureStore.getItemAsync(key);
  },
  
  async delete(key: string): Promise<void> {
    await SecureStore.deleteItemAsync(key);
  },
};
```

---

## 6. Performance

### 6.1 Listen optimieren

```typescript
// ✅ RICHTIG: FlatList mit optimalen Props
import { FlatList } from 'react-native';

<FlatList
  data={items}
  renderItem={({ item }) => <ItemCard item={item} />}
  keyExtractor={(item) => item.id}
  initialNumToRender={10}
  maxToRenderPerBatch={10}
  windowSize={5}
  getItemLayout={(data, index) => ({
    length: ITEM_HEIGHT,
    offset: ITEM_HEIGHT * index,
    index,
  })}
/>

// ❌ FALSCH: ScrollView für lange Listen
<ScrollView>
  {items.map(item => <ItemCard key={item.id} item={item} />)}
</ScrollView>
```

### 6.2 Memoization

```typescript
// Callback memoization
const handlePress = useCallback(() => {
  navigation.navigate('Details');
}, [navigation]);

// Component memoization
const MemoizedItem = memo(ItemComponent);
```

---

## 7. Checkliste vor Commit

- [ ] TypeScript hat keine Fehler
- [ ] Alle Screens haben eine sinnvolle Struktur
- [ ] Navigation funktioniert auf iOS und Android
- [ ] Performance mit FlatList optimiert
- [ ] Permissions werden korrekt angefragt
- [ ] Sensitive Daten in SecureStore
- [ ] Keine Expo SDK Deprecation Warnings