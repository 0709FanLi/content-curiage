<template>
  <div class="login-page">
    <section class="left">
      <div class="brand">
        <img class="brand-logo" :src="logoIcon" alt="logo" />
        <div class="brand-meta">
          <div class="brand-sub">医疗健康行业的AI合规增长系统</div>
        </div>
      </div>

      <div class="hero">
        <div class="hero-title">登录到</div>
        <div class="hero-brand">Curi-Compass</div>
        <div class="hero-register">
          <span class="hero-register-tip">没有账号？请先</span>
          <button class="hero-register-link" type="button" @click="go_to_register">
            注册账号
          </button>
        </div>
      </div>

      <div class="form-wrap">
        <div v-if="error_message" class="error-banner" role="alert">
          <div class="error-dot" />
          <div class="error-text">{{ error_message }}</div>
        </div>

        <el-form
          ref="login_form_ref"
          :model="login_form"
          :rules="login_rules"
          label-position="top"
          class="form"
          @submit.prevent="handle_login"
        >
          <el-form-item label="账号/邮箱" prop="username">
            <el-input
              v-model="login_form.username"
              placeholder="请输入账号/邮箱"
              size="large"
              clearable
              autocomplete="username"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="login_form.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              show-password
              autocomplete="current-password"
            />
          </el-form-item>

          <div class="assist">
            <label class="remember">
              <input v-model="remember_account" type="checkbox" />
              <span class="remember-text">记住密码</span>
            </label>
            <!-- <button class="forgot" type="button" @click="handle_forgot_password">
              忘记密码？
            </button> -->
          </div>

          <el-form-item class="submit-item">
            <el-button
              type="primary"
              size="large"
              class="submit"
              :loading="loading"
              @click="handle_login"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="copyright">
        Copyright @ 2025-2026 CuriAge. All Rights Reserved
      </div>
    </section>

    <section class="right" aria-hidden="true">
      <div class="bg-bubble b1">
        <div class="bg-bubble-inner" />
      </div>
      <div class="bg-bubble b2" />
      <div class="bg-dot d1" />
      <div class="bg-dot d2" />
      <div class="bg-dot d3" />
      <div class="bg-bubble b3" />

      <div class="right-content">
        <div class="right-title">智能AI内容创作</div>
        <div class="right-sub">让创作更简单，让想象成为现实</div>
        <ul class="right-list">
          <li><span class="bullet cyan" />AI热点情报</li>
          <li><span class="bullet blue" />智能关键帧设计</li>
          <li><span class="bullet cyan" />一键生成成品视频</li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElForm, ElMessage } from 'element-plus'

import { authApi } from '@/api'
import { useUserStore } from '@/stores'
import type { LoginRequest } from '@/types'

import logoIcon from '@/assets/icons/logo.png'

const router = useRouter()
const userStore = useUserStore()

const login_form_ref = ref<InstanceType<typeof ElForm>>()
const loading = ref(false)
const error_message = ref('')

const remember_account = ref(false)

const login_form = reactive<LoginRequest>({
  username: '',
  password: '',
})

const login_rules = {
  username: [{ required: true, message: '请输入账号/邮箱', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
}

const REMEMBER_ACCOUNT_KEY = 'remember_login_account'
const REMEMBER_ACCOUNT_VALUE_KEY = 'remember_login_account_value'

onMounted(() => {
  const remember = localStorage.getItem(REMEMBER_ACCOUNT_KEY) === 'true'
  remember_account.value = remember
  if (remember) {
    login_form.username = localStorage.getItem(REMEMBER_ACCOUNT_VALUE_KEY) || ''
  }
})

const handle_login = async () => {
  if (!login_form_ref.value) return

  error_message.value = ''
  try {
    await login_form_ref.value.validate()
    loading.value = true

    const response = await authApi.login(login_form)

    localStorage.setItem('accessToken', response.access_token)
    localStorage.setItem('refreshToken', response.refresh_token)
    // 兼容性：同时保存下划线格式
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)

    userStore.setUser(response.user)

    // 记住账号（为安全起见不存明文密码）
    localStorage.setItem(REMEMBER_ACCOUNT_KEY, String(remember_account.value))
    if (remember_account.value) {
      localStorage.setItem(REMEMBER_ACCOUNT_VALUE_KEY, login_form.username)
    } else {
      localStorage.removeItem(REMEMBER_ACCOUNT_VALUE_KEY)
    }

    ElMessage.success('登录成功')
    router.push('/inspiration')
  } catch (error: any) {
    const msg =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      '登录失败，请检查账号和密码'
    error_message.value = String(msg)
  } finally {
    loading.value = false
  }
}

const go_to_register = () => {
  router.push('/register')
}

const handle_forgot_password = () => {
  // 当前版本未提供找回流程，提示用户联系管理员（保持不打断体验）
  ElMessage.info('请联系管理员重置密码')
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background: #f5f7fa;
  display: flex;
}

.left,
.right {
  flex: 0 0 50%;
  min-width: 0;
  min-height: 100vh;
}

.left {
  background: #ffffff;
  position: relative;
  padding: 64px 0 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  width: 448px;
}

.brand-logo {
  width: 110px;
  object-fit: contain;
}

.brand-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.brand-sub {
  color: #333;
  font-size: 12px;
  line-height: 18px;
  text-align: center;
}

.hero {
  width: 448px;
  margin-top: 72px;
}

.hero-title {
  font-size: 30px;
  font-weight: 800;
  line-height: 36px;
  color: #1e2939;
  letter-spacing: 0.4px;
}

.hero-brand {
  margin-top: 0;
  font-size: 30px;
  font-weight: 800;
  line-height: 36px;
  background: linear-gradient(175.4deg, #2b7fff 0%, #00b8db 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  letter-spacing: 0.4px;
}

.hero-register {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-register-tip {
  font-size: 14px;
  color: #6a7282;
  line-height: 20px;
}

.hero-register-link {
  border: none;
  background: transparent;
  padding: 0;
  color: #2b7fff;
  font-size: 16px;
  font-weight: 600;
  line-height: 24px;
  cursor: pointer;
}

.hero-register-link:hover {
  text-decoration: underline;
}

.form-wrap {
  width: 448px;
  margin-top: 32px;
}

.error-banner {
  margin-bottom: 14px;
  border: 1px solid rgba(239, 68, 68, 0.25);
  background: rgba(239, 68, 68, 0.06);
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.error-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #ef4444;
  margin-top: 4px;
  flex: 0 0 auto;
}

.error-text {
  font-size: 13px;
  line-height: 18px;
  color: #b91c1c;
}

.form :deep(.el-form-item__label) {
  font-size: 14px;
  font-weight: 600;
  color: #364153;
  line-height: 20px;
  margin-bottom: 8px;
}

.form :deep(.el-input__wrapper) {
  height: 46px;
  border-radius: 10px;
  border: 1px solid #e1e4e8 !important;
  box-shadow: none !important;
  padding: 0 16px;
}

.form :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(43, 127, 255, 0.65) !important;
  box-shadow: 0 0 0 3px rgba(43, 127, 255, 0.12) !important;
}

.form :deep(.el-input__inner) {
  font-size: 14px;
  color: #1e2939;
}

.form :deep(.el-input__inner::placeholder) {
  color: #9ca3af;
}

.form :deep(.el-form-item__error) {
  color: #ef4444;
  font-size: 12px;
  line-height: 16px;
  padding-top: 6px;
}

.assist {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 6px 0 14px;
}

.remember {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.remember input {
  width: 16px;
  height: 16px;
  accent-color: #2b7fff;
}

.remember-text {
  font-size: 14px;
  font-weight: 600;
  color: #6a7282;
  line-height: 20px;
}

.forgot {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  color: #2b7fff;
  line-height: 16px;
  cursor: pointer;
}

.forgot:hover {
  text-decoration: underline;
}

.submit-item {
  margin-top: 0;
}

.submit {
  width: 100%;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(175.4deg, #2b7fff 0%, #00b8db 100%) !important;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -2px rgba(0, 0, 0, 0.1);
}

.copyright {
  width: 448px;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
  margin-top: auto;
}

.right {
  position: relative;
  overflow: hidden;
  background: linear-gradient(128.7deg, #e0f2fe 0%, #dbeafe 100%);
}

.bg-bubble {
  position: absolute;
  border-radius: 999px;
  background: linear-gradient(
    135deg,
    rgba(43, 127, 255, 0.15) 0%,
    rgba(0, 184, 219, 0.15) 100%
  );
}

.bg-bubble-inner {
  position: absolute;
  width: 160px;
  height: 160px;
  left: 73px;
  top: 343px;
  opacity: 0.63;
  border-radius: 999px;
  background: linear-gradient(
    135deg,
    rgba(43, 127, 255, 0.25) 0%,
    rgba(0, 184, 219, 0.25) 100%
  );
}

.b1 {
  width: 384px;
  height: 384px;
  left: 132px;
  top: -21px;
}

.b2 {
  width: 256px;
  height: 256px;
  left: 4px;
  top: 395px;
  background: linear-gradient(
    135deg,
    rgba(0, 184, 219, 0.2) 0%,
    rgba(43, 127, 255, 0.2) 100%
  );
}

.b3 {
  width: 0;
  height: 0;
}

.bg-dot {
  position: absolute;
  border-radius: 999px;
}

.d1 {
  width: 12px;
  height: 12px;
  left: 70px;
  top: 223px;
  background: rgba(0, 184, 219, 0.6);
}

.d2 {
  width: 16px;
  height: 16px;
  left: 324px;
  top: 484px;
  background: rgba(43, 127, 255, 0.5);
}

.d3 {
  width: 8px;
  height: 8px;
  left: 404px;
  top: 395px;
  background: rgba(0, 184, 219, 0.7);
}

.right-content {
  position: absolute;
  right: 96px;
  bottom: 110px;
  max-width: 520px;
}

.right-title {
  font-size: 48px;
  font-weight: 700;
  line-height: 56px;
  color: #1e2939;
  letter-spacing: 0.4px;
  white-space: normal;
}

.right-sub {
  margin-top: 18px;
  font-size: 16px;
  color: #6a7282;
  line-height: 24px;
}

.right-list {
  margin: 32px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 14px;
  color: #1e2939;
  font-size: 24px;
  letter-spacing: 1px;
}

.right-list li {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bullet {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.bullet.blue {
  background: #2b7fff;
}

.bullet.cyan {
  background: #00b8db;
}

@media (max-width: 1200px) {
  .brand,
  .hero,
  .form-wrap {
    width: 420px;
  }
  .copyright {
    width: 420px;
  }
}

@media (max-width: 980px) {
  .right {
    display: none;
  }
  .left {
    flex: 1 1 auto;
  }
  .copyright {
    margin: 22px 0 0;
    text-align: center;
  }
}
</style>

