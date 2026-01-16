<template>
  <div class="register-page">
    <section class="left">
      <div class="brand">
        <img class="brand-logo" :src="logoIcon" alt="logo" />
        <div class="brand-meta">
          <div class="brand-sub">医疗健康行业的AI合规增长系统</div>
        </div>
      </div>

      <div class="hero">
        <div class="hero-title">注册到</div>
        <div class="hero-brand">Curi-Compass</div>
        <div class="hero-login">
          <span class="hero-login-tip">已有账号？</span>
          <button class="hero-login-link" type="button" @click="go_to_login">
            立即登录
          </button>
        </div>
      </div>

      <div class="form-wrap">
        <div v-if="error_message" class="error-banner" role="alert">
          <div class="error-dot" />
          <div class="error-text">{{ error_message }}</div>
        </div>

        <el-form
          ref="register_form_ref"
          :model="register_form"
          :rules="register_rules"
          label-position="top"
          class="form"
          @submit.prevent="handle_register"
        >
          <el-form-item label="用户名/姓名" prop="username">
            <el-input
              v-model="register_form.username"
              placeholder="请输入用户名/姓名"
              size="large"
              clearable
              autocomplete="username"
            />
          </el-form-item>

          <el-form-item label="邮箱" prop="email">
            <el-input
              v-model="register_form.email"
              type="email"
              placeholder="请输入邮箱"
              size="large"
              clearable
              autocomplete="email"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="register_form.password"
              type="password"
              placeholder="请输入密码（至少8位）"
              size="large"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="register_form.confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              size="large"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>

          <el-form-item class="submit-item">
            <el-button
              type="primary"
              size="large"
              class="submit"
              :loading="loading"
              @click="handle_register"
            >
              注 册
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="copyright">
        Copyright @ 2025-2026 CuriAge. All Rights Reserved
      </div>
    </section>

    <section class="right" aria-hidden="true">
      <div class="bg-bubble b1" />
      <div class="bg-bubble b2" />
      <div class="bg-bubble b3" />
      <div class="bg-dot d1" />
      <div class="bg-dot d2" />
      <div class="bg-dot d3" />

      <div class="right-content">
        <div class="right-title">开启创作之旅</div>
        <div class="right-sub">加入我们，体验AI驱动的内容创作</div>
        <ul class="right-list">
          <li><span class="bullet blue" />快速上手，零门槛</li>
          <li><span class="bullet cyan" />多脚本风格</li>
          <li><span class="bullet blue" />视频自动合成</li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElForm } from 'element-plus'

import { authApi } from '@/api'
import logoIcon from '@/assets/icons/logo.png'

const router = useRouter()

type RegisterFormModel = {
  username: string
  email: string
  password: string
  confirmPassword: string
}

const register_form_ref = ref<InstanceType<typeof ElForm>>()
const loading = ref(false)
const error_message = ref('')

const register_form = reactive<RegisterFormModel>({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const validate_username = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  const v = String(value || '')
  if (!v.trim()) {
    callback(new Error('请输入用户名/姓名'))
    return
  }
  if (v.length < 3 || v.length > 50) {
    callback(new Error('用户名长度必须在 3-50 位之间'))
    return
  }
  callback()
}

const validate_password = (_rule: unknown, value: string, callback: (err?: Error) => void) => {
  const v = String(value || '')
  if (!v) {
    callback(new Error('请输入密码'))
    return
  }
  if (v.length < 8) {
    callback(new Error('密码长度不能少于 8 位'))
    return
  }
  const has_letter = /[a-zA-Z]/.test(v)
  const has_digit = /\d/.test(v)
  if (!has_letter || !has_digit) {
    callback(new Error('密码必须包含字母和数字'))
    return
  }
  callback()
}

const validate_confirm_password = (
  _rule: unknown,
  value: string,
  callback: (err?: Error) => void,
) => {
  const v = String(value || '')
  if (!v) {
    callback(new Error('请再次输入密码'))
    return
  }
  if (v !== register_form.password) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}

const register_rules = {
  username: [{ required: true, validator: validate_username, trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  password: [{ required: true, validator: validate_password, trigger: 'blur' }],
  confirmPassword: [{ required: true, validator: validate_confirm_password, trigger: 'blur' }],
}

const handle_register = async () => {
  if (!register_form_ref.value) return

  error_message.value = ''
  try {
    await register_form_ref.value.validate()
    loading.value = true

    await authApi.register({
      username: register_form.username,
      email: register_form.email,
      password: register_form.password,
    })

    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (error: any) {
    const msg =
      error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      '注册失败，请检查输入信息'
    error_message.value = String(msg)
  } finally {
    loading.value = false
  }
}

const go_to_login = () => {
  router.push('/login')
}
</script>

<style scoped>
.register-page {
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

.hero-login {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-login-tip {
  font-size: 14px;
  color: #6a7282;
  line-height: 20px;
}

.hero-login-link {
  border: none;
  background: transparent;
  padding: 0;
  color: #2b7fff;
  font-size: 16px;
  font-weight: 600;
  line-height: 24px;
  cursor: pointer;
}

.hero-login-link:hover {
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
  border: 1px solid #e1e4e8;
  box-shadow: none;
  padding: 0 16px;
}

.form :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(43, 127, 255, 0.65);
  box-shadow: 0 0 0 3px rgba(43, 127, 255, 0.12);
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

.submit-item {
  margin-top: 8px;
}

.submit {
  width: 100%;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(175.4deg, #2b7fff 0%, #00b8db 100%);
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

.b1 {
  width: 384px;
  height: 384px;
  left: 190px;
  top: 20px;
}

.b2 {
  width: 288px;
  height: 288px;
  left: 483px;
  top: 361px;
  background: linear-gradient(
    135deg,
    rgba(0, 184, 219, 0.18) 0%,
    rgba(43, 127, 255, 0.18) 100%
  );
}

.b3 {
  width: 176px;
  height: 176px;
  left: 373px;
  top: 222px;
  opacity: 0.9;
  background: linear-gradient(
    135deg,
    rgba(43, 127, 255, 0.25) 0%,
    rgba(0, 184, 219, 0.25) 100%
  );
}

.bg-dot {
  position: absolute;
  border-radius: 999px;
}

.d1 {
  width: 12px;
  height: 12px;
  left: 682px;
  top: 214px;
  background: rgba(43, 127, 255, 0.6);
}

.d2 {
  width: 16px;
  height: 16px;
  left: 329px;
  top: 456px;
  background: rgba(0, 184, 219, 0.5);
}

.d3 {
  width: 8px;
  height: 8px;
  left: 283px;
  top: 496px;
  background: rgba(43, 127, 255, 0.7);
}

.right-content {
  position: absolute;
  left: 70px;
  bottom: 110px;
  max-width: 520px;
}

.right-title {
  font-size: 40px;
  font-weight: 700;
  line-height: 48px;
  color: #1e2939;
  letter-spacing: 0.4px;
}

.right-sub {
  margin-top: 16px;
  font-size: 16px;
  color: #6a7282;
  line-height: 24px;
}

.right-list {
  margin: 24px 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: #1e2939;
  font-size: 20px;
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
}
</style>

